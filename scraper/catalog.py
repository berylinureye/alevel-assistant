"""
PDF 分类入库脚本

扫描 data/papers/ 下所有已下载的 PDF，解析文件名提取元数据，
将试卷记录写入 SQLite papers 表，QP 和 MS 自动配对。

用法:
    python -m scraper.catalog              # 扫描并入库
    python -m scraper.catalog --stats      # 查看入库统计
    python -m scraper.catalog --export-csv # 导出 CSV 清单
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

from scraper.config import DOWNLOAD_DIR, PAPERS, SESSION_NAMES
from scraper.taxonomy import PAPER_INFO, PAPER_TOPICS

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from questionbank.database import ensure_db, upsert_paper

# 文件名正则: 9709_s23_qp_12.pdf -> subject=9709, session=s, year=23, type=qp, paper=1, variant=2
FILENAME_RE = re.compile(
    r"^(?P<subject>\d{4})_(?P<session>[swm])(?P<year>\d{2})_(?P<type>qp|ms|er|gt|sp)_(?P<paper>\d)(?P<variant>\d)$"
)

# 从 taxonomy 获取 PAPER_META (向后兼容)
PAPER_META = {}
for _pnum, _pinfo in PAPER_INFO.items():
    _topics_dict = PAPER_TOPICS.get(_pnum, {})
    _all_topics = list(_topics_dict.keys())
    PAPER_META[_pnum] = {
        "name": _pinfo["name"],
        "level": _pinfo["level"],
        "component": _pinfo["component"],
        "topics": _all_topics,
    }


def parse_filename(stem: str) -> dict | None:
    """解析 PDF 文件名，返回元数据字典，失败返回 None"""
    m = FILENAME_RE.match(stem)
    if not m:
        return None
    year2 = int(m.group("year"))
    return {
        "subject": m.group("subject"),
        "session": m.group("session"),
        "year": 2000 + year2,
        "file_type": m.group("type"),
        "paper_num": int(m.group("paper")),
        "variant": int(m.group("variant")),
    }


def scan_papers(root: Path = DOWNLOAD_DIR) -> dict[tuple, dict]:
    """
    扫描目录，按 (subject, year, session, paper_num, variant) 分组，
    将 QP 和 MS 的路径配对在一起。

    返回: { (subject, year, session, paper_num, variant): {
        "qp_path": Path | None,
        "ms_path": Path | None,
        "meta": {...},
    }}
    """
    groups: dict[tuple, dict] = {}

    for pdf in sorted(root.rglob("*.pdf")):
        info = parse_filename(pdf.stem)
        if not info:
            continue
        # 只处理 qp 和 ms
        if info["file_type"] not in ("qp", "ms"):
            continue

        key = (info["subject"], info["year"], info["session"], info["paper_num"], info["variant"])

        if key not in groups:
            meta = PAPER_META.get(info["paper_num"], {})
            groups[key] = {
                "qp_path": None,
                "ms_path": None,
                "subject": info["subject"],
                "year": info["year"],
                "session": info["session"],
                "session_name": SESSION_NAMES.get(info["session"], info["session"]),
                "paper_num": info["paper_num"],
                "variant": info["variant"],
                "paper_name": meta.get("name", f"Paper {info['paper_num']}"),
                "level": meta.get("level", "unknown"),
                "component": meta.get("component", "unknown"),
                "topics": meta.get("topics", []),
            }

        if info["file_type"] == "qp":
            groups[key]["qp_path"] = pdf
        elif info["file_type"] == "ms":
            groups[key]["ms_path"] = pdf

    return groups


def catalog_to_db() -> dict:
    """扫描 PDF 并写入数据库 papers 表，返回统计"""
    conn = ensure_db()
    groups = scan_papers()

    stats = {
        "total_papers": 0,
        "with_qp": 0,
        "with_ms": 0,
        "paired": 0,  # 同时有 QP 和 MS
        "by_paper": {},
        "by_year": {},
        "by_level": {"AS": 0, "A2": 0},
    }

    for key, g in groups.items():
        qp = str(g["qp_path"]) if g["qp_path"] else None
        ms = str(g["ms_path"]) if g["ms_path"] else None

        upsert_paper(
            conn,
            subject_code=g["subject"],
            year=g["year"],
            session=g["session"],
            paper_num=g["paper_num"],
            variant=g["variant"],
            pdf_path=qp,
            ms_pdf_path=ms,
        )

        stats["total_papers"] += 1
        if qp:
            stats["with_qp"] += 1
        if ms:
            stats["with_ms"] += 1
        if qp and ms:
            stats["paired"] += 1

        pname = g["paper_name"]
        stats["by_paper"][pname] = stats["by_paper"].get(pname, 0) + 1

        yr = g["year"]
        stats["by_year"][yr] = stats["by_year"].get(yr, 0) + 1

        level = g["level"]
        if level in stats["by_level"]:
            stats["by_level"][level] += 1

    conn.commit()
    conn.close()
    return stats


def print_stats():
    """打印入库统计"""
    conn = ensure_db()
    rows = conn.execute("""
        SELECT paper_num, COUNT(*) as cnt,
               SUM(CASE WHEN pdf_path IS NOT NULL THEN 1 ELSE 0 END) as qp_cnt,
               SUM(CASE WHEN ms_pdf_path IS NOT NULL THEN 1 ELSE 0 END) as ms_cnt,
               MIN(year) as y1, MAX(year) as y2
        FROM papers
        GROUP BY paper_num
        ORDER BY paper_num
    """).fetchall()

    total = conn.execute("SELECT COUNT(*) as cnt FROM papers").fetchone()["cnt"]
    print(f"\n{'='*60}")
    print(f"题库试卷统计 (共 {total} 条记录)")
    print(f"{'='*60}")
    print(f"{'Paper':<30} {'记录':>6} {'QP':>6} {'MS':>6} {'年份':>12}")
    print(f"{'-'*60}")
    for row in rows:
        pname = PAPER_META.get(row["paper_num"], {}).get("name", f"Paper {row['paper_num']}")
        level = PAPER_META.get(row["paper_num"], {}).get("level", "")
        print(f"P{row['paper_num']} {pname} ({level})"[:30].ljust(30)
              + f" {row['cnt']:>6} {row['qp_cnt']:>6} {row['ms_cnt']:>6}"
              + f" {row['y1']}-{row['y2']:>4}")
    print(f"{'='*60}")
    conn.close()


def export_csv(output: str = "data/papers_catalog.csv"):
    """导出完整 CSV 清单"""
    groups = scan_papers()
    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "subject", "year", "session", "session_name",
            "paper_num", "paper_name", "variant", "level", "component",
            "topics", "has_qp", "has_ms", "qp_path", "ms_path",
        ])
        for key in sorted(groups.keys()):
            g = groups[key]
            writer.writerow([
                g["subject"], g["year"], g["session"], g["session_name"],
                g["paper_num"], g["paper_name"], g["variant"], g["level"], g["component"],
                "|".join(g["topics"]),
                bool(g["qp_path"]), bool(g["ms_path"]),
                g["qp_path"] or "", g["ms_path"] or "",
            ])
    print(f"已导出 {len(groups)} 条记录到 {out_path}")


def main():
    parser = argparse.ArgumentParser(description="PDF 分类入库")
    parser.add_argument("--stats", action="store_true", help="查看入库统计")
    parser.add_argument("--export-csv", action="store_true", help="导出 CSV 清单")
    args = parser.parse_args()

    if args.stats:
        print_stats()
        return

    if args.export_csv:
        export_csv()
        return

    # 默认：扫描并入库
    print("扫描 PDF 文件...")
    stats = catalog_to_db()
    print(f"\n入库完成!")
    print(f"  试卷记录: {stats['total_papers']}")
    print(f"  有 QP:    {stats['with_qp']}")
    print(f"  有 MS:    {stats['with_ms']}")
    print(f"  QP+MS 配对: {stats['paired']}")
    print(f"\n按 Paper 分布:")
    for pname, cnt in sorted(stats["by_paper"].items()):
        print(f"  {pname}: {cnt}")
    print(f"\n按级别分布:")
    for level, cnt in stats["by_level"].items():
        print(f"  {level}: {cnt}")

    # 入库后打印详细统计
    print_stats()


if __name__ == "__main__":
    main()
