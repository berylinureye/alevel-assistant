"""
CIE 9709 Mathematics 试卷爬虫

从 cie.fraft.cn 批量下载 A-Level 数学试卷 PDF。

策略: 由于 PDF 直链的命名规则是确定性的，
我们直接构造所有可能的文件名并逐一尝试下载。
404 的跳过，200 的保存。

用法:
    # 下载所有年份 (2015-2025)
    python -m scraper.crawler

    # 只下载 2024 年
    python -m scraper.crawler --year-start 24 --year-end 24

    # 只下载 question papers (不含 mark scheme)
    python -m scraper.crawler --types qp

    # 只下载 Paper 1 和 Paper 3
    python -m scraper.crawler --papers 1 3

    # 试运行 (不实际下载，只列出要下载的文件)
    python -m scraper.crawler --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

import httpx

from scraper.config import (
    CONCURRENCY,
    MAX_RETRIES,
    PaperInfo,
    REQUEST_DELAY,
    REQUEST_TIMEOUT,
    USER_AGENT,
    generate_all_paper_infos,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 核心下载逻辑
# ---------------------------------------------------------------------------

async def download_one(
    client: httpx.AsyncClient,
    paper: PaperInfo,
    semaphore: asyncio.Semaphore,
    delay: float = REQUEST_DELAY,
) -> bool:
    """下载单个 PDF。返回 True 表示成功，False 表示文件不存在或失败。"""

    # 跳过已下载的文件
    if paper.local_path.exists() and paper.local_path.stat().st_size > 1000:
        log.debug(f"[skip] 已存在: {paper.filename}.pdf")
        return True

    async with semaphore:
        # 请求间隔
        await asyncio.sleep(delay)

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = await client.get(paper.url, follow_redirects=True)

                if resp.status_code == 404:
                    log.debug(f"[404] {paper.filename}.pdf 不存在")
                    return False

                if resp.status_code == 200:
                    content_type = resp.headers.get("content-type", "")
                    # 确保是 PDF 而非错误页面
                    if "pdf" in content_type.lower() or resp.content[:5] == b"%PDF-":
                        paper.local_path.parent.mkdir(parents=True, exist_ok=True)
                        paper.local_path.write_bytes(resp.content)
                        size_kb = len(resp.content) / 1024
                        log.info(f"[OK] {paper} ({size_kb:.0f} KB)")
                        return True
                    else:
                        log.debug(f"[skip] {paper.filename}.pdf 响应非 PDF")
                        return False

                if resp.status_code == 429:
                    wait = 5 * attempt
                    log.warning(f"[429] 被限速，等待 {wait}s 后重试...")
                    await asyncio.sleep(wait)
                    continue

                log.warning(f"[{resp.status_code}] {paper.filename}.pdf (尝试 {attempt}/{MAX_RETRIES})")

            except (httpx.TimeoutException, httpx.ConnectError, httpx.ProxyError, httpx.RemoteProtocolError) as e:
                log.warning(f"[error] {paper.filename}.pdf: {e} (尝试 {attempt}/{MAX_RETRIES})")
                await asyncio.sleep(3 * attempt)

        return False


async def crawl(
    year_start: int = 15,
    year_end: int = 25,
    sessions: list[str] | None = None,
    papers_list: list[int] | None = None,
    file_types: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """执行批量爬取。返回统计信息。"""

    all_papers = generate_all_paper_infos(
        year_start=year_start,
        year_end=year_end,
        sessions=sessions,
        papers=papers_list,
        file_types=file_types,
    )

    log.info(f"共 {len(all_papers)} 个可能的 PDF 待检查")

    if dry_run:
        for p in all_papers:
            status = "已下载" if p.local_path.exists() else "待下载"
            print(f"  [{status}] {p}")
        already = sum(1 for p in all_papers if p.local_path.exists())
        print(f"\n已有 {already} 个, 待下载 {len(all_papers) - already} 个")
        return {"total": len(all_papers), "existing": already}

    # 过滤掉已下载的文件
    skipped = []
    to_download = []
    for p in all_papers:
        if p.local_path.exists() and p.local_path.stat().st_size > 1000:
            skipped.append(p)
        else:
            to_download.append(p)

    if skipped:
        log.info(f"已跳过 {len(skipped)} 个已下载文件")
    log.info(f"待下载 {len(to_download)} 个文件 (并发={CONCURRENCY})")

    semaphore = asyncio.Semaphore(CONCURRENCY)
    stats = {"success": 0, "not_found": 0, "failed": 0, "skipped": len(skipped)}
    completed = 0
    total = len(to_download)
    lock = asyncio.Lock()

    async def _download_and_track(client: httpx.AsyncClient, paper: PaperInfo):
        nonlocal completed
        result = await download_one(client, paper, semaphore)
        async with lock:
            completed += 1
            if result:
                stats["success"] += 1
            else:
                stats["not_found"] += 1
            if completed % 50 == 0 or completed == total:
                elapsed = time.time() - start_time
                log.info(
                    f"进度: {completed}/{total} | "
                    f"成功: {stats['success']} | "
                    f"不存在: {stats['not_found']} | "
                    f"用时: {elapsed:.0f}s"
                )

    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    ) as client:
        start_time = time.time()

        # 分批并发下载，每批 CONCURRENCY * 10 个任务
        batch_size = CONCURRENCY * 10
        for batch_start in range(0, total, batch_size):
            batch = to_download[batch_start:batch_start + batch_size]
            tasks = [_download_and_track(client, paper) for paper in batch]
            await asyncio.gather(*tasks)

        elapsed = time.time() - start_time

    log.info("=" * 60)
    log.info(f"爬取完成! 用时 {elapsed:.0f}s")
    log.info(f"  新下载: {stats['success']}")
    log.info(f"  已跳过: {stats['skipped']}")
    log.info(f"  不存在: {stats['not_found']}")
    log.info("=" * 60)

    return stats


# ---------------------------------------------------------------------------
# 便捷函数：查看已下载的文件
# ---------------------------------------------------------------------------

def list_downloaded(subject: str = "9709") -> list[Path]:
    """列出已下载的所有 PDF"""
    from scraper.config import DOWNLOAD_DIR
    paper_dir = DOWNLOAD_DIR / subject
    if not paper_dir.exists():
        return []
    return sorted(paper_dir.rglob("*.pdf"))


def download_summary(subject: str = "9709") -> dict:
    """统计已下载文件概况"""
    files = list_downloaded(subject)
    qp_count = sum(1 for f in files if "_qp_" in f.name)
    ms_count = sum(1 for f in files if "_ms_" in f.name)
    years = set()
    for f in files:
        # 从文件名提取年份: 9709_s25_qp_31.pdf -> 25 -> 2025
        parts = f.stem.split("_")
        if len(parts) >= 2:
            session_year = parts[1]  # e.g. "s25"
            year2 = session_year[1:]
            try:
                years.add(2000 + int(year2))
            except ValueError:
                pass

    total_size = sum(f.stat().st_size for f in files) / (1024 * 1024)

    return {
        "total_files": len(files),
        "question_papers": qp_count,
        "mark_schemes": ms_count,
        "years": sorted(years),
        "total_size_mb": round(total_size, 1),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="CIE 9709 Mathematics 试卷爬虫")
    parser.add_argument("--year-start", type=int, default=15, help="起始年份 (2位, 默认 15=2015)")
    parser.add_argument("--year-end", type=int, default=25, help="截止年份 (2位, 默认 25=2025)")
    parser.add_argument("--sessions", nargs="+", choices=["s", "w", "m"], help="季度筛选")
    parser.add_argument("--papers", nargs="+", type=int, choices=[1,2,3,4,5,6], help="Paper 编号筛选")
    parser.add_argument("--types", nargs="+", choices=["qp", "ms"], help="文件类型筛选")
    parser.add_argument("--dry-run", action="store_true", help="试运行，只列出文件不下载")
    parser.add_argument("--summary", action="store_true", help="显示已下载文件统计")
    args = parser.parse_args()

    if args.summary:
        info = download_summary()
        print(f"已下载文件统计:")
        print(f"  总文件数: {info['total_files']}")
        print(f"  试题卷:   {info['question_papers']}")
        print(f"  评分标准: {info['mark_schemes']}")
        print(f"  年份范围: {info['years']}")
        print(f"  总大小:   {info['total_size_mb']} MB")
        return

    asyncio.run(crawl(
        year_start=args.year_start,
        year_end=args.year_end,
        sessions=args.sessions,
        papers_list=args.papers,
        file_types=args.types,
        dry_run=args.dry_run,
    ))


if __name__ == "__main__":
    main()
