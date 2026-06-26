"""
PDF 试卷解析器

将 CIE A-Level 数学 PDF 试卷转为结构化题目数据。

流程:
    1. PDF → 高清图片 (PyMuPDF)
    2. 图片 → AI 结构化提取 (复用项目中的 AI client)
    3. Mark Scheme 匹配 (按题号对应)
    4. 写入数据库

用法:
    python -m parser.pdf_parser data/papers/9709/2025/9709_s25_qp_31.pdf
    python -m parser.pdf_parser data/papers/9709/2025/  --batch  # 批量解析整个目录
"""
from __future__ import annotations

import argparse
import io
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Optional

from PIL import Image

from questionbank.models import QuestionBankItem
from questionbank.mineru_adapter import (
    MinerUError,
    read_mineru_text,
    run_mineru_parse,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PDF → Images
# ---------------------------------------------------------------------------

def pdf_to_images(pdf_path: str | Path, dpi: int = 200) -> list[Image.Image]:
    """将 PDF 每页转为 PIL Image"""
    import fitz  # PyMuPDF

    doc = fitz.open(str(pdf_path))
    images = []
    for page_num, page in enumerate(doc):
        # 跳过封面页 (通常第 1 页是封面/说明)
        pix = page.get_pixmap(dpi=dpi)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        images.append(img)
    doc.close()
    return images


def image_to_base64(img: Image.Image, format: str = "PNG") -> str:
    """PIL Image → base64 字符串"""
    import base64
    buf = io.BytesIO()
    img.save(buf, format=format)
    return base64.b64encode(buf.getvalue()).decode()


# ---------------------------------------------------------------------------
# 文件名解析
# ---------------------------------------------------------------------------

def parse_filename(filename: str) -> dict | None:
    """
    解析 CIE 试卷文件名。
    9709_s25_qp_31.pdf → {subject, session, year, type, paper, variant}
    """
    name = Path(filename).stem
    pattern = r"^(\d{4})_([swm])(\d{2})_(qp|ms)_(\d)(\d)$"
    m = re.match(pattern, name)
    if not m:
        log.warning(f"无法解析文件名: {filename}")
        return None

    return {
        "subject": m.group(1),
        "session": m.group(2),
        "year": 2000 + int(m.group(3)),
        "file_type": m.group(4),
        "paper_num": int(m.group(5)),
        "variant": int(m.group(6)),
    }


# ---------------------------------------------------------------------------
# AI 提取 Prompt
# ---------------------------------------------------------------------------

QP_EXTRACTION_PROMPT = """\
你是一位 CIE A-Level 数学 (9709) 试卷解析专家。请仔细分析这些试卷页面图片，提取每道题的完整信息。

规则:
1. 跳过封面页和说明页（INSTRUCTIONS, INFORMATION 等）
2. 只提取正式题目（每个独立题号一条记录，子题如 (a)(b) 拆分）
3. 数学公式必须用 LaTeX 格式，用 $...$ 包裹
4. 题号格式保持原样: "1", "2(a)", "2(b)(i)"
5. 如果题目包含图表，设 has_diagram 为 true 并用文字描述图表内容
6. 难度 difficulty: 1-2=低 (基础套公式), 3=中 (多步推理), 4-5=高 (综合/证明/建模)
7. topic 必须使用下面 PAPER_TOPICS 的 key 之一 (大类)
8. subtopic 必须使用对应 paper 的 subtopic key (细分知识点)
9. tags 可以填多个细分知识点

【知识点分类参考】
- Paper 1 大类: quadratics, functions, coordinate_geometry, circular_measure, trigonometry_p1, series, differentiation_p1, integration_p1
- Paper 2 大类: algebra_p2, logarithmic_and_exponential_p2, trigonometry_p2, differentiation_p2, integration_p2, numerical_methods_p2
- Paper 3 大类: algebra_p3, logarithmic_and_exponential_p3, trigonometry_p3, differentiation_p3, integration_p3, numerical_methods_p3, differential_equations, vectors_p3, complex_numbers
- Paper 4 大类: forces_and_equilibrium, kinematics, newtons_laws, energy_work_power, momentum
- Paper 5 大类: representation_of_data, measures_of_central_tendency, measures_of_variation, permutations_and_combinations, probability, discrete_random_variables, binomial_distribution, geometric_distribution, normal_distribution
- Paper 6 大类: poisson_distribution, linear_combinations, continuous_random_variables, sampling_and_estimation, hypothesis_testing

请以 JSON 数组格式输出 (只输出数组，不要其他文字):
[
  {
    "question_number": "1",
    "question_text": "Find $\\\\int x \\\\sin(2x) \\\\, dx$.",
    "marks": 4,
    "topic": "integration_p3",
    "subtopic": "integration_by_parts",
    "difficulty": 3,
    "has_diagram": false,
    "diagram_description": null,
    "page": 2,
    "tags": ["integration_by_parts"]
  }
]

要求:
- 提取所有题目，不要遗漏
- 题目文字必须完整，包括所有条件和要求 (a) (b) 子题分别提取
- marks (分值) 在题号后面的方括号中，如 [4]
"""

MS_EXTRACTION_PROMPT = """\
你是一位 CIE A-Level 数学 Mark Scheme 解析专家。请分析这些评分标准页面，提取每道题的答案和评分点。

请以 JSON 数组格式输出:
[
  {
    "question_number": "1",
    "correct_answer": "$3x^2 \\sin(2x) + 2x^3 \\cos(2x)$",
    "marking_points": [
      "M1: 正确使用乘法法则",
      "A1: $3x^2 \\sin(2x)$ 项正确",
      "A1: $2x^3 \\cos(2x)$ 项正确",
      "A1: 最终答案完全正确"
    ],
    "common_errors": [
      "忘记链式法则导致 cos(2x) 前系数错误",
      "乘法法则方向搞反"
    ]
  }
]

评分标准中的记号含义:
- M: Method mark (方法分)
- A: Accuracy mark (准确性分)
- B: Independent mark (独立分)
"""


# ---------------------------------------------------------------------------
# AI 调用（复用项目的模型调用能力）
# ---------------------------------------------------------------------------

def extract_questions_with_ai(
    images: list[Image.Image],
    prompt: str,
    client=None,
    pages_per_batch: int = 4,
) -> list[dict]:
    """
    用 AI 视觉模型从试卷图片中提取结构化题目。
    分批处理避免单次请求图片过多导致响应被截断。
    """
    from router.models import ModelRequest, TaskType

    if client is None:
        from router.models import build_registry, ModelRole
        registry = build_registry()
        # 优先使用 vision 模型 (有视觉能力)
        client = registry.get(ModelRole.vision) or registry[ModelRole.base]

    # 跳过第1页封面
    content_images = images[1:] if len(images) > 1 else images
    if not content_images:
        return []

    all_results: list[dict] = []

    # 分批处理
    for batch_start in range(0, len(content_images), pages_per_batch):
        batch = content_images[batch_start:batch_start + pages_per_batch]
        page_nums = list(range(batch_start + 2, batch_start + 2 + len(batch)))
        batch_prompt = prompt + f"\n\n注意: 当前批次包含原 PDF 的第 {page_nums[0]}-{page_nums[-1]} 页。"

        image_b64_list = [image_to_base64(img) for img in batch]
        request = ModelRequest(
            task=TaskType.extract,
            prompt=batch_prompt,
            max_tokens=8192,
            images=image_b64_list,
        )

        try:
            response = client.call(request)
            batch_results = _parse_json_from_response(response)
            # 过滤非 dict 项 (AI 偶尔返回数字或字符串)
            valid = [item for item in batch_results if isinstance(item, dict)]
            log.info(f"    批次 {batch_start // pages_per_batch + 1}: 提取 {len(valid)} 道题 (页面 {page_nums})")
            all_results.extend(valid)
        except Exception as e:
            log.error(f"  AI 提取失败 (批次 {batch_start // pages_per_batch + 1}): {e}")

    # 按题号去重 (跨页连续题号可能重复)
    seen_qnums: set[str] = set()
    deduped: list[dict] = []
    for item in all_results:
        qn = str(item.get("question_number", ""))
        if qn and qn not in seen_qnums:
            seen_qnums.add(qn)
            deduped.append(item)

    return deduped


def extract_questions_from_text_with_ai(
    text: str,
    prompt: str,
    client=None,
    max_chars: int = 60000,
) -> list[dict]:
    """Use MinerU text output as the primary source for structured extraction."""
    from router.models import ModelRequest, TaskType

    if client is None:
        from router.models import ModelRole, build_registry
        registry = build_registry()
        client = registry.get(ModelRole.base) or registry[ModelRole.vision]

    clipped = text.strip()[:max_chars]
    if not clipped:
        return []

    text_prompt = (
        prompt
        + "\n\n以下是 MinerU 从 PDF 中按阅读顺序解析出的文本、公式和表格。"
        + "请优先基于这些内容提取题目；如果版面噪音、页眉页脚或说明文字存在，请忽略。\n\n"
        + "【MinerU 解析文本】\n"
        + clipped
    )
    request = ModelRequest(
        task=TaskType.extract,
        prompt=text_prompt,
        max_tokens=8192,
    )

    try:
        response = client.call(request)
        return [item for item in _parse_json_from_response(response) if isinstance(item, dict)]
    except Exception as e:
        log.error(f"  AI 文本提取失败: {e}")
        return []


def _parse_json_from_response(text: str) -> list[dict]:
    """从 AI 响应中提取 JSON 数组"""
    from utils.json_repair import parse_json_array

    try:
        repaired = parse_json_array(text)
        return [item for item in repaired if isinstance(item, dict)]
    except Exception:
        pass

    # 尝试直接解析
    text = text.strip()
    if text.startswith("["):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    # 尝试从 markdown code block 中提取
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试找到第一个 [ 和最后一个 ]
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    log.error("无法从 AI 响应中解析 JSON")
    return []


def _env_truthy(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------------------
# 完整解析流程
# ---------------------------------------------------------------------------

def parse_question_paper(
    qp_path: str | Path,
    ms_path: str | Path | None = None,
    client=None,
    dpi: int = 200,
    use_mineru: bool | None = None,
    require_mineru: bool | None = None,
    include_mark_scheme: bool | None = None,
) -> list[QuestionBankItem]:
    """
    解析一份试卷 PDF，返回结构化题目列表。

    参数:
        qp_path:  Question Paper PDF 路径
        ms_path:  Mark Scheme PDF 路径 (可选，用于匹配答案)
        client:   AI 模型客户端
        dpi:      PDF 转图片分辨率
    """
    qp_path = Path(qp_path)
    info = parse_filename(qp_path.name)
    if not info:
        log.error(f"无法解析文件名: {qp_path.name}")
        return []

    log.info(f"解析试卷: {qp_path.name}")

    mineru_enabled = _env_truthy("QUESTIONBANK_USE_MINERU") if use_mineru is None else use_mineru
    mineru_required = (
        _env_truthy("QUESTIONBANK_REQUIRE_MINERU")
        if require_mineru is None
        else require_mineru
    )
    should_parse_mark_scheme = (
        _env_truthy("QUESTIONBANK_PARSE_MARK_SCHEME", default=True)
        if include_mark_scheme is None
        else include_mark_scheme
    )

    questions_raw: list[dict] = []
    if mineru_enabled:
        try:
            log.info("  MinerU 解析 PDF...")
            mineru_result = run_mineru_parse(qp_path)
            mineru_text = read_mineru_text(mineru_result)
            if mineru_text.strip():
                log.info(f"  MinerU 提取文本 {len(mineru_text)} 字符，开始结构化题目...")
                questions_raw = extract_questions_from_text_with_ai(
                    mineru_text, QP_EXTRACTION_PROMPT, client
                )
            if not questions_raw:
                message = "MinerU did not produce structured questions."
                if mineru_required:
                    raise MinerUError(message)
                log.warning(f"  {message} Falling back to image extraction.")
        except MinerUError as exc:
            if mineru_required:
                raise
            log.warning(f"  MinerU 不可用或解析失败，回退到图片/VL 路径: {exc}")

    if not questions_raw:
        # 1. PDF → 图片
        log.info("  转换 PDF 为图片...")
        qp_images = pdf_to_images(qp_path, dpi=dpi)
        log.info(f"  共 {len(qp_images)} 页")

        # 2. AI 提取题目
        log.info("  AI 提取题目...")
        questions_raw = extract_questions_with_ai(qp_images, QP_EXTRACTION_PROMPT, client)
    log.info(f"  提取到 {len(questions_raw)} 道题")

    # 3. 如果有 Mark Scheme，匹配答案
    ms_data = {}
    if should_parse_mark_scheme and ms_path and Path(ms_path).exists():
        log.info(f"  解析 Mark Scheme: {Path(ms_path).name}")
        ms_images = pdf_to_images(ms_path, dpi=dpi)
        ms_raw = extract_questions_with_ai(ms_images, MS_EXTRACTION_PROMPT, client)
        ms_data = {
            str(item["question_number"]): item
            for item in ms_raw
            if isinstance(item, dict) and "question_number" in item
        }
        log.info(f"  Mark Scheme 提取到 {len(ms_data)} 道题的答案")

    # 4. 组装 QuestionBankItem
    items = []
    for q in questions_raw:
        qnum = q.get("question_number", "")
        ms_match = ms_data.get(qnum, {})

        item = QuestionBankItem(
            question_number=qnum,
            parent_number=_extract_parent(qnum),
            question_text=q.get("question_text", ""),
            marks=q.get("marks", 0),
            topic=q.get("topic", "unknown"),
            subtopic=q.get("subtopic"),
            difficulty=q.get("difficulty", 3),
            has_diagram=q.get("has_diagram", False),
            diagram_description=q.get("diagram_description"),
            correct_answer=ms_match.get("correct_answer"),
            marking_points=ms_match.get("marking_points"),
            common_errors=ms_match.get("common_errors"),
            subject_code=info["subject"],
            year=info["year"],
            session=info["session"],
            paper_num=info["paper_num"],
            variant=info["variant"],
            source_page=q.get("page"),
            parse_confidence=0.8,  # 默认置信度，后续可由 AI 自评
            tags=q.get("tags", []),
        )
        items.append(item)

    log.info(f"  完成! 共 {len(items)} 道结构化题目")
    return items


def _extract_parent(qnum: str) -> str | None:
    """从题号提取父题号: '2(a)(i)' → '2', '3(b)' → '3', '1' → None"""
    m = re.match(r"^(\d+)", qnum)
    if m and qnum != m.group(1):
        return m.group(1)
    return None


def find_mark_scheme(qp_path: Path) -> Path | None:
    """根据 Question Paper 路径找到对应的 Mark Scheme"""
    ms_name = qp_path.name.replace("_qp_", "_ms_")
    ms_path = qp_path.parent / ms_name
    if ms_path.exists():
        return ms_path
    return None


# ---------------------------------------------------------------------------
# 批量入库
# ---------------------------------------------------------------------------

def parse_and_store(
    qp_path: str | Path,
    client=None,
    db_path: str | Path | None = None,
    skip_if_parsed: bool = True,
    use_mineru: bool | None = None,
    require_mineru: bool | None = None,
    include_mark_scheme: bool | None = None,
) -> int:
    """解析试卷并存入数据库。返回入库题目数。"""
    from questionbank.database import ensure_db, upsert_paper, insert_question

    qp_path = Path(qp_path)
    info = parse_filename(qp_path.name)
    if not info or info["file_type"] != "qp":
        log.warning(f"跳过非 QP 文件: {qp_path.name}")
        return 0

    ms_path = find_mark_scheme(qp_path)

    # 检查是否已解析过
    if skip_if_parsed:
        conn = ensure_db()
        row = conn.execute(
            """SELECT p.id, COUNT(q.id) as cnt
               FROM papers p LEFT JOIN questions q ON q.paper_id = p.id
               WHERE p.subject_code=? AND p.year=? AND p.session=? AND p.paper_num=? AND p.variant=?
               GROUP BY p.id""",
            (info["subject"], info["year"], info["session"], info["paper_num"], info["variant"]),
        ).fetchone()
        conn.close()
        if row and row["cnt"] > 0:
            log.info(f"  跳过 (已解析 {row['cnt']} 题): {qp_path.name}")
            return 0

    # 解析
    items = parse_question_paper(
        qp_path,
        ms_path,
        client,
        use_mineru=use_mineru,
        require_mineru=require_mineru,
        include_mark_scheme=include_mark_scheme,
    )
    if not items:
        return 0

    # 入库
    conn = ensure_db()
    try:
        paper_id = upsert_paper(
            conn,
            subject_code=info["subject"],
            year=info["year"],
            session=info["session"],
            paper_num=info["paper_num"],
            variant=info["variant"],
            pdf_path=str(qp_path),
            ms_pdf_path=str(ms_path) if ms_path else None,
        )

        count = 0
        for item in items:
            item.paper_id = paper_id
            insert_question(conn, item)
            count += 1

        conn.commit()
        log.info(f"入库完成: {qp_path.name} → {count} 道题")
        return count

    except Exception as e:
        conn.rollback()
        log.error(f"入库失败: {e}")
        return 0
    finally:
        conn.close()


def batch_parse(
    directory: str | Path,
    client=None,
    use_mineru: bool | None = None,
    require_mineru: bool | None = None,
    include_mark_scheme: bool | None = None,
) -> dict:
    """批量解析一个目录下的所有 QP PDF"""
    directory = Path(directory)
    qp_files = sorted(directory.rglob("*_qp_*.pdf"))

    log.info(f"找到 {len(qp_files)} 个 Question Paper 文件")

    stats = {"total": len(qp_files), "success": 0, "failed": 0, "questions": 0}

    for i, qp in enumerate(qp_files, 1):
        log.info(f"\n[{i}/{len(qp_files)}] {qp.name}")
        try:
            count = parse_and_store(
                qp,
                client,
                use_mineru=use_mineru,
                require_mineru=require_mineru,
                include_mark_scheme=include_mark_scheme,
            )
            if count > 0:
                stats["success"] += 1
                stats["questions"] += count
            else:
                stats["failed"] += 1
        except Exception as e:
            log.error(f"  处理失败: {e}")
            stats["failed"] += 1

    log.info(f"\n批量解析完成: {stats}")
    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    # 加载 .env 配置 (DASHSCOPE_API_KEY 等)
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    parser = argparse.ArgumentParser(description="CIE A-Level 数学 PDF 解析器")
    parser.add_argument("path", help="PDF 文件或目录路径")
    parser.add_argument("--batch", action="store_true", help="批量解析目录下所有 QP")
    parser.add_argument("--store", action="store_true", help="解析结果存入数据库 (默认输出 JSON)")
    parser.add_argument("--dpi", type=int, default=200, help="PDF 转图片 DPI")
    parser.add_argument("--use-mineru", action="store_true", help="优先使用 MinerU 解析 PDF 文本")
    parser.add_argument("--require-mineru", action="store_true", help="MinerU 失败时不回退到视觉路径")
    parser.add_argument("--skip-mark-scheme", action="store_true", help="只解析题目与标签，跳过 Mark Scheme")
    args = parser.parse_args()

    path = Path(args.path)

    if args.batch or path.is_dir():
        batch_parse(
            path,
            use_mineru=args.use_mineru or None,
            require_mineru=args.require_mineru or None,
            include_mark_scheme=False if args.skip_mark_scheme else None,
        )
    elif args.store:
        count = parse_and_store(
            path,
            use_mineru=args.use_mineru or None,
            require_mineru=args.require_mineru or None,
            include_mark_scheme=False if args.skip_mark_scheme else None,
        )
        print(f"\n入库完成: {count} 道题")
    else:
        items = parse_question_paper(
            path,
            find_mark_scheme(path),
            use_mineru=args.use_mineru or None,
            require_mineru=args.require_mineru or None,
            include_mark_scheme=False if args.skip_mark_scheme else None,
        )
        print(json.dumps(
            [item.model_dump(exclude_none=True) for item in items],
            ensure_ascii=False,
            indent=2,
        ))


if __name__ == "__main__":
    main()
