"""
图表题 & 提取不确定 的"不判错"安全网。

场景 A — 学生以作图作答（stem-and-leaf / histogram / box-plot 等）：
  extractor 无法可靠转录图形，grader 看到空 student_answer 会判错。
  统一改成「不判分、标 needs_review、正确答案写作图步骤」。

场景 B — 提取置信度偏低 + student_answer 基本为空：
  学生很可能答了但没被识别上。若 LLM 仍判错，改判 needs_review。

两个场景合并在 pipeline.py 一处分支里调用本模块。
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from models.schemas import GradeResult, QuestionType
from router.models import ModelRequest, TaskType

if TYPE_CHECKING:
    from models.schemas import QuestionData
    from router.models import ModelClient

_log = logging.getLogger("grader.diagram")


_DIAGRAM_LABEL_CN = {
    "stem_leaf": "茎叶图",
    "histogram": "直方图（frequency density histogram）",
    "box_plot": "箱线图（box-and-whisker plot）",
    "cumulative_frequency": "累积频率曲线",
    "scatter": "散点图",
    "bar_chart": "条形图",
    "other": "统计图",
}


_DIAGRAM_INSTRUCTION_PROMPT = """\
You are a senior A-Level statistics teacher. A student answered the following question by
drawing a {diagram_type_cn}. Our OCR cannot reliably read the drawing, so we cannot auto-grade
it. Your job is to produce the REFERENCE DRAWING STEPS a student should follow, so the student
can self-check.

Question:
{question_text}

Working the student wrote (may be empty or partial):
{working_steps}

Output a concise Chinese step-by-step guide (≤ 220 字), strictly following this structure:
1. 轴 / 关键量的定义（横纵轴、stems 的选取、组距等）
2. 需要先算出的关键数值（中位数、四分位数、频率密度……），用 $...$ 包裹公式
3. 绘图要点（刻度、标签、Key、异常值标记等）
4. 常见失分点（≤ 2 条）

Do NOT judge the student's drawing as correct or incorrect — you cannot see it clearly.
Do NOT output markdown headers, code fences, or "学生作答如何"之类的评论。
Wrap every math symbol in $...$ (e.g. $Q_1$, $\\bar{{x}}$, $n+1 \\over 4$).
Keep it actionable and short.
"""


def _call_model(client: "ModelClient", prompt: str) -> str:
    req = ModelRequest(task=TaskType.grade, prompt=prompt, max_tokens=800)
    try:
        return (client.call(req) or "").strip()
    except Exception as e:  # noqa: BLE001
        _log.warning("diagram reference generation failed: %s", e)
        return ""


def build_diagram_review_grade(
    question: "QuestionData",
    client: "ModelClient",
) -> GradeResult:
    """学生以作图作答 → 不判对错、标 needs_review、correct_answer 填作图步骤。"""
    dt = (question.diagram_type or "other").lower()
    dt_cn = _DIAGRAM_LABEL_CN.get(dt, _DIAGRAM_LABEL_CN["other"])

    working_steps_text = "\n".join(question.working_steps) if question.working_steps else "（无）"
    prompt = _DIAGRAM_INSTRUCTION_PROMPT.format(
        diagram_type_cn=dt_cn,
        question_text=question.question_text or "",
        working_steps=working_steps_text,
    )
    reference = _call_model(client, prompt)
    if not reference:
        reference = f"本题要求作{dt_cn}，系统暂无法自动识别手绘结果，请老师复核图形是否正确。"

    full_score = float(question.marks) if question.marks and question.marks > 0 else 1.0
    short_feedback = (
        f"本题为{dt_cn}作图题，系统无法可靠识别手绘图形，已标记需教师复核。"
        f"下方为参考作图步骤，请对照自检。"
    )

    return GradeResult(
        question_number=question.question_number,
        question_type=QuestionType.statistics,
        is_correct=False,
        score=0.0,
        full_score=full_score,
        error_type="pending_review",
        knowledge_tags=[f"diagram:{dt}"],
        needs_review=True,
        short_feedback=short_feedback,
        grading_confidence=0.3,
        correct_answer=reference,
        syllabus_topics=[],
        relevant_formulas=[],
        student_feedback=(
            f"你画了一张{dt_cn}。自动批改暂时无法读懂手绘图，"
            f"已把参考作图步骤放在“正确答案”里，请自己对照检查。"
        ),
        teacher_feedback=(
            f"- Error: 图表题（{dt_cn}）未自动判分\n"
            f"- Gap: 需人工核对图形（轴标/刻度/Key/异常值）\n"
            f"- Action: 对照参考步骤当面复核"
        ),
    )


def build_low_confidence_review_grade(
    question: "QuestionData",
    base_grade: GradeResult,
    reference_answer: str | None,
) -> GradeResult:
    """提取置信度偏低 + LLM 判错 → 改判 needs_review，保留参考答案。

    不新起 LLM 调用——参考答案优先用 base_grade.correct_answer，调用方也可传进来覆盖。
    """
    ref = (reference_answer or base_grade.correct_answer or "").strip() or None
    short_feedback = (
        "学生作答可能未被完整识别（识别置信度偏低），已标记需教师复核，"
        "避免误判为错误。下方为参考答案，请对照原图复核。"
    )
    # 复制一份，避免修改原对象
    g = base_grade.model_copy(update={
        "is_correct": False,
        "score": min(base_grade.score, base_grade.full_score * 0.5),
        "error_type": "pending_review",
        "needs_review": True,
        "short_feedback": short_feedback,
        "correct_answer": ref,
    })
    return g


def is_answer_effectively_empty(question: "QuestionData") -> bool:
    """student_answer 实际是否为空（或仅占位）。working_steps ≤ 1 条简短时也视为'基本没抽到'。"""
    sa = (question.student_answer or "").strip()
    placeholder = sa.lower() in ("", "(no answer provided)", "no answer", "none", "n/a", "-", "—")
    steps = [s for s in (question.working_steps or []) if s and s.strip()]
    minimal_working = len(steps) <= 1 and sum(len(s) for s in steps) < 20
    return placeholder and minimal_working
