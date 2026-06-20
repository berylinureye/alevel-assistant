"""
Feedback generator：GradeResult → QuestionFeedback

规则：
- 正确题不调 LLM，返回固定短语
- 错误题一次调用同时产出 student_feedback + teacher_feedback
- 失败最多重试 max_retries 次，之后降级为基于 short_feedback 的模板，不抛异常
- 所有输出经过 strip_latex_and_markdown 后处理，确保纯文本无标记
"""
from __future__ import annotations

from models.schemas import GradeResult, QuestionFeedback
from router.models import ModelClient, ModelRequest, TaskType
from utils.json_repair import parse_json_object
from utils.text_cleanup import strip_latex_and_markdown

# ---------------------------------------------------------------------------
# Prompt — 要求纯文本 bullet points，禁止 LaTeX 和 Markdown
# ---------------------------------------------------------------------------
_FEEDBACK_PROMPT = """\
You are generating feedback for an A-Level maths question. Use ONLY the data below (do not invent facts):

  question_type      : {question_type}
  error_type         : {error_type}
  knowledge_tags     : {knowledge_tags}
  short_feedback     : {short_feedback}
  question_text      : {question_text}
  student_answer     : {student_answer}
  working_steps      : {working_steps}
  relevant_formulas  : {relevant_formulas}

Return ONLY a valid JSON object:

{{
  "student_feedback": "...",
  "teacher_feedback": "..."
}}

=== RULES FOR BOTH FIELDS ===
- Use Chinese for main text. English OK for A-Level terms (e.g. Combined Data, Binomial).
- All math expressions MUST be wrapped in LaTeX $...$. Examples: $x^2$, $\\frac{{a}}{{b}}$, $\\pi$, $\\sqrt{{x}}$, $\\sum x^2$
- No Markdown syntax (no **, ##, `).

=== student_feedback (for the student) ===
Write a SHORT bullet-point list. Max 3 bullets. Each bullet is one clear sentence.

If correct:
- One bullet stating the key concept tested. NO praise or encouragement.
Example: "- 做对了，组合数据的均值和标准差都算得很准确。"

If incorrect:
- Bullet 1: What went wrong — if working_steps are provided, identify the SPECIFIC step where
  the error occurred (say "第X步..." referencing the actual step content), not a generic message
- Bullet 2: The correct approach (hint, not full solution)
- Bullet 3: What to review
Example:
"- 求合并标准差时，$\\sum x^2$ 算错了，漏加了均值的平方项。
- 试试用 $\\sum x^2 = n(s^2 + \\bar{{x}}^2)$ 来反推。
- 建议复习 Combined Data 那节的公式变形。"

HARD CONSTRAINTS for student_feedback:
- No markdown symbols: ###, **, *, ~~, `, or any heading/bold/italic markers
- No praise or encouragement: do NOT write "做得好", "很棒", "漂亮", "继续保持", "加油", "太棒了"
- Tone: objective and concise, like a brief examiner note
- If correct: one sentence only, max 30 Chinese characters
- If incorrect: max 100 Chinese characters total across all bullets
- No numbered steps like "第一步", "第二步"; refer to specific content instead

=== teacher_feedback (for the teacher) ===
Write exactly 3 short bullets:
- Error: [what exactly went wrong]
- Gap: [which knowledge point is weak]
- Action: [one specific teaching recommendation]

If correct: just write "- 掌握良好，无需额外关注。"

Example for incorrect:
"- Error: $\\sum x^2$ 计算时遗漏均值平方项
- Gap: 方差公式的逆向变形不熟练
- Action: 安排 2-3 道从已知均值和标准差反推 $\\sum x^2$ 的练习"
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CORRECT_BY_TYPE: dict[str, tuple[str, str]] = {
    "differentiation":   ("- 微分法则运用正确。",   "- 微分部分掌握良好。"),
    "integration":       ("- 积分计算准确。",       "- 积分部分掌握良好。"),
    "stationary_points": ("- 驻点求解步骤完整。",   "- 驻点分析掌握良好。"),
}
_CORRECT_DEFAULT = ("- 本题作答正确。", "- 掌握良好，无需额外关注。")


def _correct_feedback(question_number: str, question_type: str = "") -> QuestionFeedback:
    student, teacher = _CORRECT_BY_TYPE.get(question_type, _CORRECT_DEFAULT)
    return QuestionFeedback(
        question_number  = question_number,
        student_feedback = student,
        teacher_feedback = teacher,
    )


def _fallback_from_short(question_number: str, short_feedback: str, error_type: str) -> QuestionFeedback:
    """Build a usable fallback from short_feedback when LLM feedback generation fails."""
    short = strip_latex_and_markdown(short_feedback).strip() if short_feedback else ""
    err = error_type or "unknown"

    if short:
        student = f"- {short}\n- 建议仔细检查解题过程，重新尝试。"
    else:
        student = "- 这道题需要重新检查，请仔细对照解题步骤。\n- 如有疑问可以问老师。"

    teacher = f"- Error: {err}\n- Gap: 需人工判断\n- Action: 建议面批，了解具体错误原因"

    return QuestionFeedback(
        question_number  = question_number,
        student_feedback = student,
        teacher_feedback = teacher,
    )


# Backward-compatible alias used by older tests/scripts.
_fallback_feedback = _fallback_from_short


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_feedback(
    grade: GradeResult,
    client: ModelClient,
    question_text: str = "",
    student_answer: str = "",
    working_steps: list[str] | None = None,
    max_retries: int = 2,
) -> QuestionFeedback:
    if grade.is_correct:
        return _correct_feedback(grade.question_number, grade.question_type.value)

    prompt = _FEEDBACK_PROMPT.format(
        question_type      = grade.question_type.value,
        error_type         = grade.error_type or "unknown",
        knowledge_tags     = ", ".join(grade.knowledge_tags) if grade.knowledge_tags else "none",
        short_feedback     = grade.short_feedback or "",
        question_text      = question_text or "(not provided)",
        student_answer     = student_answer or "(not provided)",
        working_steps      = "\n".join(working_steps) if working_steps else "(无解题步骤)",
        relevant_formulas  = ", ".join(grade.relevant_formulas) if grade.relevant_formulas else "none",
    )
    request = ModelRequest(task=TaskType.grade, prompt=prompt, max_tokens=512)

    for attempt in range(max_retries + 1):
        try:
            raw  = client.call(request)
            data = parse_json_object(raw)
            return QuestionFeedback(
                question_number  = grade.question_number,
                student_feedback = data["student_feedback"],
                teacher_feedback = data["teacher_feedback"],
            )
        except Exception:
            if attempt < max_retries:
                # Retry with stricter prompt
                request = ModelRequest(
                    task=TaskType.grade,
                    prompt="IMPORTANT: Return ONLY valid JSON, no markdown, no code fences.\n\n" + prompt,
                    max_tokens=512,
                )
            else:
                return _fallback_from_short(
                    grade.question_number,
                    grade.short_feedback,
                    grade.error_type,
                )
