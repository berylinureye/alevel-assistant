"""
解题思路生成器：批改完成后自动生成，缓存到 record 中。
单模型调用，不用多 Agent。
"""
from __future__ import annotations

import logging
import re
import time
from typing import TYPE_CHECKING

from grader.solution_prompts import get_active_prompt
from grader.solution_verifier import (
    clean_solution_output,
    has_expected_solution_structure,
    has_forbidden_solution_style,
    verify_and_fix_solution,
)
from router.models import ModelClient, ModelRequest, TaskType

if TYPE_CHECKING:
    from models.schemas import GradeResult, QuestionData

_log = logging.getLogger("solution_explainer")

_FALLBACK = "解题思路生成失败，请向老师咨询。"
_STRICT_STYLE_APPENDIX = """\

【额外硬性约束】
- 只输出纯净的标准解法，不要输出批改稿、点评稿或提示词回显
- 不要出现“学生的作答”“学生答案”“正确答案”“批改反馈”“要求”“重要”“内部参考”等字样
- 不要评价学生，不要复述学生错误，不要给复习建议
- 严格按编号列表输出：
    1. $式子$ —— 一句解释
    2. $式子$ —— 一句解释
    ...
    ∴ $答案$    （证明题写 "∴ 命题得证"）
- 至多 6 条；解释 ≤ 20 中文字符
- 所有数学符号、变量、希腊字母都必须用 LaTeX 包裹在 $...$ 内（写 $\\alpha$ 而不是 α）
"""


_PROOF_KEYWORDS = re.compile(
    r"\b(?:show that|prove|hence show|deduce that|demonstrate)\b|证明|求证",
    re.IGNORECASE,
)


def _is_proof_question(question_text: str) -> bool:
    """Proof/show-that 题不要求 '因此，答案为 X'，允许 '得证'/'结论成立' 收尾。"""
    if not question_text:
        return False
    return bool(_PROOF_KEYWORDS.search(question_text))


def generate_solution(
    question: QuestionData,
    grade_result: GradeResult,
    client: ModelClient,
    timeout: int = 60,
) -> str | None:
    """
    生成解题思路。批改完成后立即调用，结果存入 record。
    单模型调用，不用多 Agent。
    返回 solution_text，失败返回 None（不阻塞主流程）。
    """
    prompt_template = get_active_prompt()

    # 组装 feedback 文本
    feedback_parts = []
    if grade_result.short_feedback:
        feedback_parts.append(grade_result.short_feedback)
    if grade_result.student_feedback:
        feedback_parts.append(grade_result.student_feedback)
    feedback = "\n".join(feedback_parts) if feedback_parts else "无"

    # 孤儿子题补父题题干，保证模型看到完整上下文
    q_text_for_prompt = question.question_text or "(无题目文字)"
    if question.parent_stem:
        q_text_for_prompt = (
            f"【父题题干（本小题依赖的共同条件）】\n{question.parent_stem}\n\n"
            f"【本小题】\n{q_text_for_prompt}"
        )

    prompt = prompt_template.format(
        question_text=q_text_for_prompt,
        student_answer=question.student_answer or "(未作答)",
        correct_answer=grade_result.correct_answer or "(未提供)",
        feedback=feedback,
        is_correct_text="是" if grade_result.is_correct else "否",
    )

    request = ModelRequest(
        task=TaskType.grade,
        prompt=prompt,
        max_tokens=1500,
        temperature=0.3,
    )

    _t_start = time.monotonic()
    # 保证 LLM 调用本身有墙钟上限（ModelClient 默认 120s，这里再压一次）
    per_call_timeout = max(15, int(timeout * 0.7))
    try:
        client.timeout = per_call_timeout  # type: ignore[attr-defined]
    except Exception:
        pass

    try:
        raw = client.call(request).strip()
        if not raw:
            _log.warning("解题思路生成返回空")
            return None

        # 后处理 Step 1: 清理自我纠结内容 (< 10ms)
        cleaned = clean_solution_output(raw)

        # 后处理 Step 2: SymPy 验证并修正算术错误 (< 500ms)
        verified, fixes = verify_and_fix_solution(cleaned)
        fixed_count = sum(1 for f in fixes if f["fixed"])
        if fixed_count:
            _log.info("解题思路计算修正 %d 处: %s", fixed_count, [f for f in fixes if f["fixed"]])

        # 后处理 Step 3: 结构/答案检查（新模板 PROMPT_E：编号列表 + ∴ 收尾，不再区分证明/常规）
        is_proof = _is_proof_question(question.question_text)
        has_forbidden_style = has_forbidden_solution_style(verified)
        structure_invalid = not has_expected_solution_structure(verified)
        answer_mismatch = (
            not is_proof
            and bool(grade_result.correct_answer)
            and not _solution_contains_answer(verified, grade_result.correct_answer)
        )
        elapsed = time.monotonic() - _t_start
        remaining = timeout - elapsed
        # 只在 (有问题) AND (还有足够预算跑一次完整重试) 时才重试
        need_retry = has_forbidden_style or structure_invalid or answer_mismatch
        if need_retry and remaining < 12:
            _log.warning(
                "解题思路首版格式不完美但预算剩 %.1fs，跳过重试直接放行（除非含敏感内容）",
                remaining,
            )
            if has_forbidden_style:
                _log.warning("解题思路含禁止内容且无预算重试，已拦截")
                return None
            return verified
        if need_retry:
            reasons: list[str] = []
            if has_forbidden_style:
                reasons.append("输出含有禁止的点评式结构")
            if structure_invalid:
                reasons.append("输出未按约定的教学结构组织")
            if answer_mismatch:
                reasons.append(f"最终结果未推出正确答案 {grade_result.correct_answer}")
            _log.warning(
                "解题思路需要重生成（剩余预算 %.1fs）：%s",
                remaining, "；".join(reasons),
            )
            retry_prompt = prompt + _STRICT_STYLE_APPENDIX
            if answer_mismatch and grade_result.correct_answer:
                retry_prompt += (
                    "\n\n【答案硬性约束】上次你生成的解题思路最终结果没有等于正确答案 "
                    f"{grade_result.correct_answer}。必须让你的推导最后一步清清楚楚等于 "
                    f"{grade_result.correct_answer}，任何中间近似都不能让最终答案偏离。"
                )
            retry_per_call = max(10, int(remaining * 0.9))
            try:
                client.timeout = retry_per_call  # type: ignore[attr-defined]
            except Exception:
                pass
            retry_req = ModelRequest(
                task=TaskType.grade,
                prompt=retry_prompt,
                max_tokens=1500,
                temperature=0.1,
            )
            try:
                raw2 = client.call(retry_req).strip()
                if raw2:
                    cleaned2 = clean_solution_output(raw2)
                    verified2, _ = verify_and_fix_solution(cleaned2)
                    retry_has_forbidden_style = has_forbidden_solution_style(verified2)
                    retry_structure_ok = has_expected_solution_structure(verified2)
                    retry_answer_ok = (
                        is_proof
                        or not grade_result.correct_answer
                        or _solution_contains_answer(verified2, grade_result.correct_answer)
                    )
                    if not retry_has_forbidden_style and retry_structure_ok and retry_answer_ok:
                        _log.info("解题思路重生成成功：结构合规且答案一致")
                        return verified2
                    if retry_has_forbidden_style:
                        _log.warning("重生成仍包含禁止的点评式结构，丢弃")
                    elif retry_answer_ok:
                        _log.info("重生成内容可用但格式不完全匹配，降级放行")
                        return verified2
                    elif not retry_structure_ok:
                        _log.warning("重生成仍不符合约定教学结构，丢弃")
                    elif not retry_answer_ok:
                        _log.warning("重生成仍未推出正确答案，丢弃")
            except Exception as e:
                _log.warning("解题思路重生成失败: %s", e)

        if has_forbidden_solution_style(verified):
            _log.warning("解题思路包含禁止的点评式结构，已拦截")
            return None
        if answer_mismatch:
            _log.warning("解题思路未推出正确答案，已拦截")
            return None
        if structure_invalid:
            _log.info("解题思路格式未完全命中模板，降级放行")
        return verified
    except Exception as e:
        _log.warning("生成解题思路失败: %s", e)
        return None


_AGGREGATOR_PROMPT = """\
你是数学解题思路的汇编员。下面是 {n_agents} 位数学老师独立批改这道题时留下的分析素材——有些指出错因、有些给出正确答案、有些提到关键公式。你的任务不是重新解题，而是综合这些素材，产出一份**面向学生的标准解题思路**。

【题目】
{question_text}

【正确答案（多数老师的共识）】
{correct_answer}

【多位老师的批改分析（仅作你综合参考的原始素材，严禁照抄、严禁点评学生）】
{deliberations_block}

【各老师提到的关键公式】
{formulas_block}

输出格式（严格遵守，除此之外不写任何内容）：

1. $式子$ —— 一句解释
2. $式子$ —— 一句解释
3. $式子$ —— 一句解释
4. $式子$ —— 一句解释
∴ $答案$

规则：
- 从题目条件直接推导到答案，只写"标准解法"，不要提学生、不要复述批改反馈
- 至多 6 条，少即是多；每条"式子"必须是完整等式或关系式
- 解释 ≤ 20 中文字符
- 数学内容全部 $...$ 包裹；希腊字母写 \\alpha \\theta \\pi（不要 α θ π）
- 中间步骤保留分数/根号/π 等精确形式，只在最后一步转小数
- 最终 ∴ 一行必须等于给定的正确答案；证明题用 "∴ 命题得证" 结尾
- 直接输出编号列表，不要前言、不要标题、不要"【解题思路】"这类包装
"""


def _format_deliberations_block(deliberations: list[dict]) -> str:
    lines: list[str] = []
    for d in deliberations:
        agent = d.get("agent", "?")
        ca = (d.get("correct_answer") or "").strip()
        sf = (d.get("short_feedback") or "").strip()
        stu = (d.get("student_feedback") or "").strip()
        et = d.get("error_type") or ""
        parts = []
        if ca:
            parts.append(f"正确答案={ca}")
        if et and et not in ("correct", "unknown", None):
            parts.append(f"错因={et}")
        if sf:
            # 限长避免某个 agent 的冗长 feedback 挤爆 prompt
            parts.append(f"点评={sf[:160]}")
        if stu and stu != sf:
            parts.append(f"对学生={stu[:160]}")
        if parts:
            lines.append(f"- [{agent}] " + "；".join(parts))
    return "\n".join(lines) if lines else "（无可用分析）"


def _format_formulas_block(deliberations: list[dict]) -> str:
    seen: set[str] = set()
    out: list[str] = []
    for d in deliberations:
        for f in d.get("relevant_formulas") or []:
            key = str(f).strip()
            if key and key not in seen:
                seen.add(key)
                out.append(f"- {key}")
                if len(out) >= 8:
                    break
        if len(out) >= 8:
            break
    return "\n".join(out) if out else "（无）"


def generate_solution_from_deliberations(
    question: QuestionData,
    grade_result: GradeResult,
    client: ModelClient,
    timeout: int = 30,
) -> str | None:
    """
    基于 5 个 grading agent 已经产出的推理素材，用一个更快的模型做「汇编」。
    比 generate_solution 快得多（模型只做格式化+综合，不需要从零解题），
    典型 5-10s 返回。后处理沿用 clean / SymPy 验证 / 格式检查。

    失败或 deliberations 为空时返回 None，调用方应 fallback 到 generate_solution。
    """
    deliberations: list[dict] = list(getattr(grade_result, "_agent_deliberations", []) or [])
    if not deliberations:
        return None

    # 父题题干补进去（孤儿子题场景）
    q_text = question.question_text or "(无题目文字)"
    if getattr(question, "parent_stem", None):
        q_text = f"【父题题干】\n{question.parent_stem}\n\n【本小题】\n{q_text}"

    prompt = _AGGREGATOR_PROMPT.format(
        n_agents=len(deliberations),
        question_text=q_text,
        correct_answer=grade_result.correct_answer or "(未知)",
        deliberations_block=_format_deliberations_block(deliberations),
        formulas_block=_format_formulas_block(deliberations),
    )

    request = ModelRequest(
        task=TaskType.grade,
        prompt=prompt,
        max_tokens=900,
        temperature=0.2,
    )

    per_call_timeout = max(15, int(timeout * 0.9))
    try:
        client.timeout = per_call_timeout  # type: ignore[attr-defined]
    except Exception:
        pass

    _t0 = time.monotonic()
    try:
        raw = client.call(request).strip()
    except Exception as e:
        _log.warning("aggregator call failed: %s", e)
        return None
    if not raw:
        return None

    cleaned = clean_solution_output(raw)
    verified, fixes = verify_and_fix_solution(cleaned)
    fixed_count = sum(1 for f in fixes if f["fixed"])
    if fixed_count:
        _log.info("aggregator SymPy fixed %d calc(s)", fixed_count)

    if has_forbidden_solution_style(verified):
        _log.warning("aggregator 输出含禁止内容，丢弃（调用方应 fallback）")
        return None

    _log.info(
        "aggregator solution done in %.1fs (structure_ok=%s, len=%d)",
        time.monotonic() - _t0,
        has_expected_solution_structure(verified),
        len(verified),
    )
    # 结构不完美也放行（前端能看到 ∴ 结论就行，样式降级）
    return verified


def _extract_number(s: str) -> float | None:
    import re as _re
    if not s:
        return None
    s = s.replace("\\approx", "").replace("≈", "").strip().strip("$ ").strip()
    s = _re.sub(r"\\frac\s*\{(-?\d+(?:\.\d+)?)\}\s*\{(-?\d+(?:\.\d+)?)\}",
                lambda m: f"{m.group(1)}/{m.group(2)}", s)
    # fraction a/b
    m = _re.search(r"(-?\d+(?:\.\d+)?)\s*/\s*(-?\d+(?:\.\d+)?)", s)
    if m:
        try:
            a, b = float(m.group(1)), float(m.group(2))
            if b != 0:
                return a / b
        except ValueError:
            pass
    nums = _re.findall(r"-?\d+(?:\.\d+)?", s)
    if nums:
        try:
            return float(nums[-1])
        except ValueError:
            return None
    return None


def _solution_contains_answer(solution_text: str, correct_answer: str) -> bool:
    """Check that solution_text arrives at the correct numeric answer (tolerance 1%)."""
    import math as _math
    if not solution_text or not correct_answer:
        return True  # can't check, don't flag
    target = _extract_number(correct_answer)
    if target is None:
        # Non-numeric answer (e.g. a transformation description) — fall back to substring check
        # Strip LaTeX wrappers and compare short fragment
        key = correct_answer.strip().strip("$").strip()
        return len(key) < 4 or key[:30] in solution_text
    # Scan solution for any number close to target (last one is most likely the conclusion)
    candidates = []
    import re as _re
    for m in _re.finditer(r"-?\d+(?:\.\d+)?", solution_text):
        try:
            candidates.append(float(m.group(0)))
        except ValueError:
            continue
    # also evaluate any a/b fractions
    for m in _re.finditer(r"(-?\d+(?:\.\d+)?)\s*/\s*(-?\d+(?:\.\d+)?)", solution_text):
        try:
            a, b = float(m.group(1)), float(m.group(2))
            if b != 0:
                candidates.append(a / b)
        except ValueError:
            continue
    # also \frac{a}{b}
    for m in _re.finditer(r"\\frac\s*\{(-?\d+(?:\.\d+)?)\}\s*\{(-?\d+(?:\.\d+)?)\}", solution_text):
        try:
            a, b = float(m.group(1)), float(m.group(2))
            if b != 0:
                candidates.append(a / b)
        except ValueError:
            continue

    return any(_math.isclose(c, target, rel_tol=0.01, abs_tol=0.02) for c in candidates)


# ---------------------------------------------------------------------------
# 追问对话 prompt
# ---------------------------------------------------------------------------

_FOLLOWUP_SYSTEM = """\
你是一位耐心的数学辅导老师，正在帮学生理解一道题。

【题目】
{question_text}

【学生的作答】
{student_answer}

【正确答案】
{correct_answer}

【你之前给学生讲的解题思路】
{solution_text}

学生有进一步的疑问，请耐心解答：
- 针对学生的具体问题回答，不要重复整个解题过程
- 如果学生问某一步不理解，重点解释那一步
- 用简单的语言，必要时举例子
- 用 LaTeX 写数学公式（用 $ 包裹）
- 语言：中文"""


def build_followup_prompt(
    question: QuestionData,
    grade_result: GradeResult,
    solution_text: str,
    conversation: list[dict],
    user_message: str,
) -> str:
    """
    构建追问对话的完整 prompt。
    将系统上下文 + 历史对话 + 新消息拼成单条 prompt（因为 ModelClient.call 只接受单 prompt）。
    只保留最近 5 轮对话，防止过长。
    """
    system_context = _FOLLOWUP_SYSTEM.format(
        question_text=question.question_text or "(无题目文字)",
        student_answer=question.student_answer or "(未作答)",
        correct_answer=grade_result.correct_answer or "(未提供)",
        solution_text=solution_text,
    )

    # 只保留最近 5 轮
    recent = conversation[-10:] if len(conversation) > 10 else conversation

    parts = [system_context, "\n以下是和学生的对话："]
    for msg in recent:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "user":
            parts.append(f"\n学生：{content}")
        else:
            parts.append(f"\n老师：{content}")

    parts.append(f"\n学生：{user_message}\n老师：")

    return "\n".join(parts)
