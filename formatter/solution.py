"""
Solution Explainer：生成中文逐步解题思路。
按需调用，不在主批改流程中执行。
"""
from __future__ import annotations

from grader.solution_verifier import (
    clean_solution_output,
    has_expected_solution_structure,
    has_forbidden_solution_style,
)
from router.models import ModelClient, ModelRequest, TaskType

_EXPLAIN_PROMPT = """\
你是一位 A-Level 数学老师，正在用中文给 16-18 岁学生写一道题的标准解法。

题目：{question_text}

以下内容仅供内部参考，帮助你校验思路，绝对不要在输出中直接提及或复述：
- 学生答案：{student_answer}
- 学生步骤：{working_steps}
- 判定结果：{is_correct}
- 错误类型：{error_type}
- 得分：{score} / {full_score}
- 参考正确答案：{correct_answer}

请只输出“纯净的标准解法”，要求如下：
{structure_rules}

通用规则：
- 不要出现“学生答案”“正确答案”“批改反馈”“重要”“要求”“内部参考”等标题或字段
- 不要点评学生，不要分析学生错因，不要布置复习任务
- 所有数学公式必须用 LaTeX 写在 $...$ 中
- 不要用 Markdown 标题、代码块或项目符号
- 如果提供了参考正确答案，你的最后结果必须与它一致

现在开始输出，直接给出可以展示给学生的正式解法。
"""

_FALLBACK = "解题思路生成失败，请向老师咨询。"
_STRICT_RETRY_APPENDIX = """\

【重生成附加约束】
- 上一版输出含有禁止的点评稿/提示词回显风格
- 这一版必须删掉所有元信息，只保留正式解题过程
- 从第一步推导直接写到最终答案，不要再出现任何“学生答案/正确答案/批改反馈/重要/要求”字样
"""

_WRONG_STRUCTURE_RULES = """\
1. 第一行必须写“关键思路：……”，用 1-2 句话点明解题抓手
2. 分步推导部分必须使用“第 1 步：”“第 2 步：”这样的格式，逐步推导到答案
3. 然后写“易错提醒：……”，只用一句中性提醒，帮助学生避免常见混淆
4. 最后一行前写“因此，答案为 ……”给出最终结果
5. 结尾再写“自检：……”，只用一句话提醒优先回查哪一步
"""

_CORRECT_STRUCTURE_RULES = """\
1. 第一行必须写“关键思路：……”，用 1-2 句话点明解题抓手
2. 分步推导部分必须使用“第 1 步：”“第 2 步：”这样的格式，逐步推导到答案
3. 最后一行写“因此，答案为 ……”给出最终结果
4. 不要写“易错提醒”或“自检”，保持紧凑
"""

_PROOF_CORRECT_STRUCTURE_RULES = """\
1. 第一行必须写“关键思路：……”，用 1-2 句话点明证明抓手
2. 分步推导部分必须使用“第 1 步：”“第 2 步：”这样的格式，逐步推出结论
3. 最后一行不要写“因此，答案为”，改写成“所以 ……，结论成立。”或“这就证明了 ……”
4. 不要写“易错提醒”或“自检”，保持紧凑
"""


def _is_proof_like_question(question_text: str, correct_answer: str | None) -> bool:
    text = f"{question_text}\n{correct_answer or ''}".lower()
    return any(
        token in text
        for token in ("show that", "prove", "证明", "求证", "verify that")
    )


def generate_solution_explanation(
    question_text: str,
    student_answer: str,
    working_steps: list[str],
    is_correct: bool,
    error_type: str | None,
    score: float,
    full_score: float,
    correct_answer: str | None,
    client: ModelClient,
    max_retries: int = 1,
) -> str:
    require_mistake_section = not is_correct
    is_proof_like = _is_proof_like_question(question_text, correct_answer)
    structure_rules = (
        _PROOF_CORRECT_STRUCTURE_RULES if is_correct and is_proof_like
        else _CORRECT_STRUCTURE_RULES if is_correct
        else _WRONG_STRUCTURE_RULES
    )
    prompt = _EXPLAIN_PROMPT.format(
        question_text=question_text,
        student_answer=student_answer or "(未作答)",
        working_steps="\n".join(working_steps) if working_steps else "(无解题步骤)",
        is_correct="正确" if is_correct else "错误",
        error_type=error_type or "unknown",
        score=score,
        full_score=full_score,
        correct_answer=correct_answer or "(未提供)",
        structure_rules=structure_rules,
    )
    cleaned_draft = ""
    best_candidate = ""

    for attempt in range(max_retries + 1):
        try:
            if attempt == 0:
                active_prompt = prompt
            else:
                active_prompt = prompt + _STRICT_RETRY_APPENDIX
                if cleaned_draft:
                    active_prompt += (
                        "\n\n【待改写草稿】\n"
                        f"{cleaned_draft}\n\n"
                        "请保留数学内容，只把它改写成上面要求的正式结构。"
                    )
            # max_tokens 从 8192 降到 1500：解题思路是短编号列表，没必要留这么多额度，
            # 避免模型跑满导致网关超时（部署端常见 502/504）
            request = ModelRequest(task=TaskType.grade, prompt=active_prompt, max_tokens=1500)
            raw = client.call(request).strip()
            cleaned = clean_solution_output(raw)
            cleaned_draft = cleaned
            if cleaned and not has_forbidden_solution_style(cleaned):
                best_candidate = cleaned
            if (
                cleaned
                and not has_forbidden_solution_style(cleaned)
                and has_expected_solution_structure(
                    cleaned,
                    require_mistake_section=require_mistake_section,
                    require_self_check=require_mistake_section,
                    allow_proof_conclusion=is_correct and is_proof_like,
                )
            ):
                # Keep LaTeX — frontend KaTeX renderer handles $...$
                return cleaned
        except Exception:
            if attempt == max_retries:
                return best_candidate or _FALLBACK
    return best_candidate or _FALLBACK
