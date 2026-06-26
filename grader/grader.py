"""
Grader：QuestionData → GradeResult

流程：classify → get_prompt → LLM 调用 → 解析 → GradeResult

GraderBackend Protocol 预留，后续可换模型或批改策略。
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

import logging
import re

from models.schemas import GradeResult, QuestionData, QuestionType
from router.models import ModelClient, ModelRequest, TaskType
from grader.classifier import classify_question
from grader.prompts import get_prompt
from grader.confidence import calibrate_confidence
from utils.json_repair import parse_json_object
from grader.solution_verifier import clean_solution_output

_log = logging.getLogger("grader")


@runtime_checkable
class GraderBackend(Protocol):
    def grade(self, question: QuestionData, client: ModelClient, task: TaskType) -> GradeResult: ...


_STATISTICS_KEYWORDS = (
    "mean", "median", "standard deviation", "variance", "quartile",
    "interquartile", "iqr", "frequency", "mid-interval", "mid interval",
    "estimate the mean", "∑x", "∑y", "Σx", "Σy", "sum_x", "sum of", "s.d",
    "mode ", " mode.", " mode,", "deviation", "histogram", "stem-and-leaf",
    "cumulative frequency", "box-and-whisker", "box plot", "outlier",
)


def _looks_like_statistics(text: str) -> bool:
    if not text:
        return False
    low = text.lower()
    return any(kw in low for kw in _STATISTICS_KEYWORDS)


def _apply_probability_verifier(
    grade: GradeResult,
    question: QuestionData,
    client: ModelClient,
) -> bool | None:
    """Deterministic check for discrete probability questions (esp. conditional)."""
    from verifier.probability_verifier import verify_probability
    try:
        vr = verify_probability(
            question_text=question.question_text,
            student_answer=question.student_answer,
            working_steps=question.working_steps or [],
            client=client,
            parent_stem=question.parent_stem,
        )
    except Exception as e:
        _log.debug("Q%s probability verifier skipped: %s", question.question_number, e)
        return None

    if not vr.verified:
        _log.info("Q%s prob-verifier: inconclusive (%s)", question.question_number, vr.detail)
        return None

    _log.info("Q%s prob-verifier: %s", question.question_number, vr.detail)

    # Unanswered / non-numeric student answer: still correct the LLM's expected answer.
    if vr.student_matches is None:
        if vr.primary_answer:
            old = grade.correct_answer
            new_ca = f"${vr.primary_answer}$"
            if (old or "").strip() != new_ca.strip():
                grade.correct_answer = new_ca
                _log.info(
                    "Q%s prob-verifier: correcting LLM correct_answer %s → %s",
                    question.question_number, old, grade.correct_answer,
                )
        return None

    if vr.student_matches and not grade.is_correct:
        _log.warning(
            "Q%s prob-verifier OVERRIDE: student matches independent calc (%s). Flipping to True.",
            question.question_number, vr.exact_fraction,
        )
        grade.is_correct = True
        grade.score = grade.full_score
        grade.error_type = "correct"
        grade.short_feedback = (
            (grade.short_feedback or "") + " [已通过概率验证修正：学生答案与独立计算一致]"
        ).strip()
        if vr.primary_answer:
            grade.correct_answer = f"${vr.primary_answer}$"
        return True

    if not vr.student_matches and grade.is_correct:
        _log.warning(
            "Q%s prob-verifier: LLM said correct but student does NOT match (%s). Flagging review.",
            question.question_number, vr.exact_fraction,
        )
        grade.needs_review = True
        return False

    if not vr.student_matches and not grade.is_correct:
        if vr.primary_answer:
            old = grade.correct_answer
            grade.correct_answer = f"${vr.primary_answer}$"
            if (old or "").strip() != grade.correct_answer.strip():
                _log.info(
                    "Q%s prob-verifier: correcting LLM correct_answer %s → %s",
                    question.question_number, old, grade.correct_answer,
                )
        return False

    return True


def _apply_statistics_verifier(
    grade: GradeResult,
    question: QuestionData,
    client: ModelClient,
) -> bool | None:
    """独立数值验证统计题。返回与 LLM 判分是否一致（喂给 confidence 校准）。"""
    from verifier.statistics_verifier import verify_statistics
    try:
        vr = verify_statistics(
            question_text=question.question_text,
            student_answer=question.student_answer,
            working_steps=question.working_steps or [],
            client=client,
            parent_stem=question.parent_stem,
        )
    except Exception as e:
        _log.debug("Q%s statistics verifier skipped: %s", question.question_number, e)
        return None

    if not vr.verified:
        _log.info("Q%s stat-verifier: inconclusive (%s)", question.question_number, vr.detail)
        return None

    # Even when the student didn't submit a numeric answer (student_matches is None),
    # the verifier's deterministic primary_answer is still trustworthy — use it to
    # correct an LLM-hallucinated correct_answer (e.g. grader wrote "IQR=1.3" but
    # actual IQR=1.5). This especially matters for unanswered questions where the
    # student would otherwise only see the wrong "expected" answer.
    if vr.student_matches is None:
        _log.info("Q%s stat-verifier: %s (no student numeric answer)", question.question_number, vr.detail)
        if vr.primary_answer:
            old = grade.correct_answer
            new_ca = f"${vr.primary_answer}$"
            if (old or "").strip() != new_ca.strip():
                grade.correct_answer = new_ca
                _log.info(
                    "Q%s stat-verifier: correcting LLM correct_answer %s → %s",
                    question.question_number, old, grade.correct_answer,
                )
        return None

    _log.info("Q%s stat-verifier: %s", question.question_number, vr.detail)

    if vr.student_matches and not grade.is_correct:
        _log.warning(
            "Q%s stat-verifier OVERRIDE: LLM said incorrect but student matches independent calc (%s). Flipping to True.",
            question.question_number, vr.primary_answer,
        )
        grade.is_correct = True
        grade.score = grade.full_score
        grade.error_type = "correct"
        grade.needs_review = False
        grade.grading_confidence = max(float(grade.grading_confidence or 0.0), 0.95)
        answer_note = f"独立计算结果为 {vr.primary_answer}。" if vr.primary_answer else ""
        grade.short_feedback = "答案正确，已通过独立统计公式校验。"
        grade.student_feedback = (
            "答案正确。你的最终答案或关键演算与独立统计公式计算一致，"
            "本题应给满分。"
        )
        grade.teacher_feedback = (
            "统计数值校验确认学生作答正确。"
            f"{answer_note}"
            " 已覆盖原模型的错误判定。"
        )
        if vr.primary_answer:
            grade.correct_answer = f"${vr.primary_answer}$"
        return True

    if not vr.student_matches and grade.is_correct:
        _log.warning(
            "Q%s stat-verifier: LLM said correct but student does NOT match independent calc (acceptable=%s). Flagging needs_review.",
            question.question_number, vr.acceptable_answers,
        )
        grade.needs_review = True
        return False

    if not vr.student_matches and not grade.is_correct:
        if vr.primary_answer:
            old = grade.correct_answer
            grade.correct_answer = f"${vr.primary_answer}$"
            if old != grade.correct_answer:
                _log.info(
                    "Q%s stat-verifier: correcting LLM correct_answer %s → %s",
                    question.question_number, old, grade.correct_answer,
                )
        return False

    return True


def verify_and_calibrate(
    grade: GradeResult,
    question: QuestionData,
    q_type: QuestionType,
    stat_client: ModelClient | None = None,
) -> GradeResult:
    """SymPy 验证 + confidence 校准。从 grade_question 中提取，供多 agent 投票后复用。
    stat_client: 若提供且题型为 statistics，额外做数值验证。"""
    import time as _time

    # SymPy 等价校验的题型白名单。凡答案是代数表达式/数值的题型都值得跑一次——
    # verify_equivalence 自己会对无法解析的输入静默返回 inconclusive，不会误伤。
    _SYMPY_SAFE_TYPES = {
        "differentiation", "integration", "algebra", "stationary_points",
        "trigonometry", "vectors", "sequences_series",
        "coordinate_geometry", "logarithms_exponentials",
    }
    _t_sympy = _time.monotonic()
    sympy_agrees: bool | None = None
    if q_type.value in _SYMPY_SAFE_TYPES:
        try:
            from verifier.math_verifier import verify_grade, verify_equivalence
            vr = verify_grade(
                question_text=question.question_text,
                student_answer=question.student_answer or "",
                correct_answer=grade.correct_answer,
                question_type=q_type.value,
                is_correct=grade.is_correct,
            )
            if vr.verified:
                sympy_agrees = vr.sympy_agrees

                if sympy_agrees is False and vr.sympy_answer:
                    if "DISAGREES" in (vr.detail or ""):
                        _log.warning(
                            "Q%s: SymPy overriding LLM correct_answer. LLM=%s → SymPy=%s",
                            question.question_number, grade.correct_answer, vr.sympy_answer,
                        )
                        grade.correct_answer = f"${vr.sympy_answer}$"
                        grade.needs_review = True

                        student_vs_sympy = verify_equivalence(
                            vr.sympy_answer, question.student_answer or ""
                        )
                        if student_vs_sympy.verified and student_vs_sympy.sympy_agrees is not None:
                            old_correct = grade.is_correct
                            grade.is_correct = student_vs_sympy.sympy_agrees
                            if old_correct != grade.is_correct:
                                _log.warning(
                                    "Q%s: Correctness changed after SymPy override: %s → %s",
                                    question.question_number, old_correct, grade.is_correct,
                                )
                                if grade.is_correct:
                                    grade.error_type = "correct"
                                    grade.short_feedback = "答案正确。"
                    else:
                        # SymPy 说"不等价"但没独立算出答案（detail 没 DISAGREES 前缀）。
                        # 这种情况多半是 parse/format 失败：LLM 的 correct_answer 带
                        # LaTeX 标签（如 "Radius $r=5$"、"centre $C(4,-2)$"）或学生答案
                        # 带 "C:(4,-2)" 这样的前缀，SymPy 靠字符串切逗号比较会假阴性。
                        # 不是真的数学分歧，降级成 info 日志，不 flag needs_review 来
                        # 避免无谓地把题升级到慢模型 review。
                        _log.info(
                            "Q%s: SymPy couldn't verify LLM grading (likely format/parse issue, not math disagreement). %s",
                            question.question_number, vr.detail,
                        )
        except Exception as e:
            _log.debug("SymPy verification skipped: %s", e)
    else:
        _log.info("Q%s SymPy: skipped (type=%s not in safe types)", question.question_number, q_type.value)

    _log.info("Q%s SymPy: %.1fs", question.question_number, _time.monotonic() - _t_sympy)

    # --- Statistics numeric verifier (deterministic Python cross-check) ---
    # Run whenever the question text hints at statistics data (don't trust classifier alone —
    # we've seen "statistics" be misclassified as sequences_series / coordinate_geometry).
    _stat_scan_text = question.question_text or ""
    if question.parent_stem:
        _stat_scan_text = question.parent_stem + "\n" + _stat_scan_text
    if stat_client is not None and _looks_like_statistics(_stat_scan_text):
        _t_stat = _time.monotonic()
        stat_agrees = _apply_statistics_verifier(grade, question, stat_client)
        _log.info("Q%s stat-verifier: %.1fs", question.question_number, _time.monotonic() - _t_stat)
        if stat_agrees is not None and sympy_agrees is None:
            sympy_agrees = stat_agrees

    # --- Probability verifier (discrete distributions, conditional probability) ---
    # Runs whenever the text mentions probability; safe to skip silently if not applicable.
    from verifier.probability_verifier import looks_like_discrete_probability
    if stat_client is not None and looks_like_discrete_probability(_stat_scan_text):
        _t_prob = _time.monotonic()
        prob_agrees = _apply_probability_verifier(grade, question, stat_client)
        _log.info("Q%s prob-verifier: %.1fs", question.question_number, _time.monotonic() - _t_prob)
        if prob_agrees is not None and sympy_agrees is None:
            sympy_agrees = prob_agrees

    # --- Fraction-simplification check (deterministic, no LLM) ---
    # Flags unsimplified fractions in the student's final answer and deducts a
    # single presentation mark for full_score >= 3. Never affects already-wrong
    # answers. Cheap (regex + gcd) — runs on every question.
    try:
        from verifier.simplification_verifier import apply_simplification_check
        if apply_simplification_check(grade, question):
            _log.info(
                "Q%s simplification: flagged unsimplified fractions (score adjusted: %s)",
                question.question_number, grade.score,
            )
    except Exception as e:
        _log.debug("Q%s simplification check skipped: %s", question.question_number, e)

    grade.grading_confidence = calibrate_confidence(grade, sympy_agrees=sympy_agrees)
    return grade


def grade_question(
    question: QuestionData,
    client: ModelClient,
    task: TaskType = TaskType.grade,
    base_grade: GradeResult | None = None,
    skip_verification: bool = False,
    q_type: QuestionType | None = None,
    allow_llm_classification: bool = True,
    parse_attempts: int = 3,
    request_retries: int = 2,
) -> GradeResult:
    import time as _time
    _t_start = _time.monotonic()

    # Step 1: 题型识别（可外部传入避免每个 agent 重复分类）
    # 孤儿子题 classify 也喂父题题干，否则很容易错类
    if q_type is None:
        classify_text = question.question_text
        if question.parent_stem:
            classify_text = f"{question.parent_stem}\n\n{classify_text}"
        q_type = classify_question(
            classify_text,
            client if allow_llm_classification else None,
        )
        _log.info("Q%s classify: %s (%.1fs)", question.question_number, q_type.value, _time.monotonic() - _t_start)

    # Step 2: 取对应 prompt（task 决定 grade / review 模板，review 传入 base_grade）
    marks_hint = ""
    if question.marks and question.marks > 0:
        marks_hint = f"\n\nMark allocation: [{question.marks}] marks. full_score MUST be {question.marks}.\n"

    # 孤儿子题（裸 "(i)"/"(a)"）补上父题题干，否则 grader 看到空白条件会直接判错
    parent_block = ""
    if question.parent_stem:
        parent_block = (
            "\n[Parent question stem — shared setup this sub-part depends on]\n"
            f"{question.parent_stem}\n"
            "[End of parent stem. The specific sub-part to grade follows.]\n\n"
        )

    mark_scheme_block = ""
    if question.mark_scheme_context:
        mark_scheme_block = (
            "\n[Official mark scheme context]\n"
            "Use this official mark scheme as the primary scoring guide. "
            "Apply M/A/B marks and follow-through rules when they are present, "
            "then explain any deduction in student-friendly language.\n"
            f"{question.mark_scheme_context}\n"
            "[End official mark scheme context]\n\n"
        )

    prompt = get_prompt(q_type, task, base_grade=base_grade).format(
        question_text=mark_scheme_block + parent_block + question.question_text + marks_hint,
        student_answer=question.student_answer or "(no answer provided)",
        working_steps=(
            "\n".join(question.working_steps)
            if question.working_steps
            else "(no working shown)"
        ),
    )

    # Step 3: 调用 LLM
    request = ModelRequest(
        task=task,
        prompt=prompt,
        max_tokens=4096,
        max_retries=max(0, request_retries),
    )

    # Step 4: 解析结果（不让脏输出/截断直接打断整条 pipeline）
    data: dict | None = None
    last_error: Exception | None = None
    for attempt in range(max(1, parse_attempts)):
        _t_llm = _time.monotonic()
        raw = client.call(request)
        _log.info("Q%s LLM call attempt %d: %.1fs (%s)", question.question_number, attempt+1, _time.monotonic() - _t_llm, client.model_id)
        try:
            data = parse_json_object(raw)
            break
        except Exception as e:
            last_error = e
            # 用同一份 schema prompt，但强约束输出格式再试
            strict = (
                "IMPORTANT: Return ONLY a valid JSON object. "
                "No markdown, no code fences, no extra text.\n\n"
                + prompt
            )
            request = ModelRequest(
                task=task,
                prompt=strict,
                max_tokens=2048,
                max_retries=max(0, request_retries),
            )

    if data is None:
        # 兜底：返回可用的 GradeResult，让上层走 review 或人工检查，而不是直接崩溃
        return GradeResult(
            question_number=question.question_number,
            question_type=q_type,
            is_correct=False,
            score=0.0,
            full_score=5.0,
            error_type="unknown",
            knowledge_tags=[],
            needs_review=True,
            short_feedback=f"Automated grading output malformed; manual review required. ({last_error})",
            grading_confidence=0.0,
            syllabus_topics=[],
            relevant_formulas=[],
        )

    # Step 5: needs_review：LLM 建议 OR 提取置信度低
    needs_review = bool(data.get("needs_review", False))
    if question.confidence < 0.7:
        needs_review = True

    raw_topics = data.get("syllabus_topics", [])
    if not isinstance(raw_topics, list):
        raw_topics = []
    syllabus_topics = [t for t in raw_topics if isinstance(t, dict)]

    raw_formulas = data.get("relevant_formulas", [])
    if not isinstance(raw_formulas, list):
        raw_formulas = []
    relevant_formulas = [clean_solution_output(str(f)) for f in raw_formulas]

    # 清理所有文本字段中的犹豫/自我纠正内容
    raw_correct_answer = data.get("correct_answer")
    raw_short_feedback = data.get("short_feedback", "")
    raw_student_feedback = data.get("student_feedback")
    raw_teacher_feedback = data.get("teacher_feedback")

    grade = GradeResult(
        question_number    = question.question_number,
        question_type      = q_type,
        is_correct         = bool(data.get("is_correct", False)),
        score              = float(data.get("score", 0)),
        full_score         = float(data.get("full_score", 5)),
        error_type         = data.get("error_type", "unknown") or "unknown",
        knowledge_tags     = data.get("knowledge_tags", []),
        needs_review       = needs_review,
        short_feedback     = clean_solution_output(raw_short_feedback) if raw_short_feedback else "",
        grading_confidence = float(data.get("grading_confidence", 0.5)),
        correct_answer     = clean_solution_output(raw_correct_answer) if raw_correct_answer else raw_correct_answer,
        student_feedback   = clean_solution_output(raw_student_feedback) if raw_student_feedback else raw_student_feedback,
        teacher_feedback   = clean_solution_output(raw_teacher_feedback) if raw_teacher_feedback else raw_teacher_feedback,
        syllabus_topics    = syllabus_topics,
        relevant_formulas  = relevant_formulas,
    )

    # --- Post-processing: enforce consistency ---
    # 1. full_score：题面显示分数时以其为准；未显示分数则统一按 1 分计，避免 LLM 编造分值
    if question.marks and question.marks > 0:
        grade.full_score = float(question.marks)
    else:
        if grade.full_score != 1.0:
            _log.info("Q%s: no marks on paper, defaulting full_score 1.0 (LLM returned %.1f)",
                      question.question_number, grade.full_score)
        grade.full_score = 1.0

    # 1.5 Safety net: 学生答案与正确答案文本一致时，LLM 说错了也强制修正
    #     避免 "2√3 vs 2√3" 但 is_correct=False 的乌龙。
    #
    # 但要很保守，避免这种 bug 链:
    #   (1) VL 把没作答的题幻觉出一个 student_answer 如 "y = x"（受题干 "y = mx + c"
    #       提示词模板污染），
    #   (2) grader 因为信息不足也返回一个简化的 correct_answer = "y = x"，
    #   (3) 这里文本一致 → 翻成 correct，
    #   (4) 后面 score 一致性修复再把 0 分拉成满分。
    # 防御策略：
    #   - LLM 给 0 分的不翻（给 0 说明 grader 看到真问题，不是纯 format 不匹配）
    #   - 学生答案必须含至少一个数字/符号，不能是 "y = x" 这种全字母的短表达
    #   - 学生答案必须够长（去空白后 ≥ 6 字符）
    if (
        not grade.is_correct
        and grade.score > 0
        and question.student_answer
        and grade.correct_answer
        and not getattr(grade, "unanswered", False)
    ):
        _sa = re.sub(r'[\s$\\{}\'"]+', '', (question.student_answer or "")).strip().lower()
        _ca = re.sub(r'[\s$\\{}\'"]+', '', (grade.correct_answer or "")).strip().lower()
        # 只有当答案含"特异性"内容时才允许 text-match 覆盖，避免 VL 对空白题幻觉成
        # "y = x" / "y = -x + 3" 这种通用短式和 grader 幻觉的 correct_answer 碰巧撞上。
        # 特异性信号（任一即可）：
        #   - 多位数字 (\d{2,})，如 "169"、"13"、"24/210"
        #   - 根号、pi、无穷、分数线、不等号等非字母数字运算符
        #   - 答案长度 ≥ 12 字符（通用 y = mx + c 形的短式全部低于这个阈值）
        _has_multi_digit = bool(re.search(r"\d{2,}", _sa))
        _has_special = bool(re.search(r"[√π∞≈≤≥≠/]|\\sqrt|\\frac|\\pi|\\infty", _sa))
        _is_distinctive = _has_multi_digit or _has_special or len(_sa) >= 12
        if _sa and _ca and _sa == _ca and _is_distinctive:
            _log.warning(
                "Q%s: student_answer == correct_answer textually ('%s') but LLM said incorrect → overriding",
                question.question_number, question.student_answer,
            )
            grade.is_correct = True
            grade.error_type = "correct"
            grade.needs_review = False
            grade.grading_confidence = max(float(grade.grading_confidence or 0.0), 0.9)
            grade.short_feedback = "答案正确。"
            grade.student_feedback = "答案正确。你的答案与系统识别出的标准答案一致。"
            grade.teacher_feedback = "学生答案与标准答案文本一致，已覆盖原模型的错误判定。"
        elif _sa and _ca and _sa == _ca:
            # 文本撞上但答案太通用（如 "y = x"），很可能是 VL + grader 双重幻觉。
            # 不翻转，但降分并标 needs_review 让老师复核。
            _log.warning(
                "Q%s: text match ('%s') but too generic to trust — keeping LLM 'incorrect' verdict",
                question.question_number, question.student_answer,
            )
            grade.needs_review = True

    # 2. Enforce is_correct ↔ score consistency
    if grade.is_correct and grade.error_type in ("correct", None):
        # Correct answer with complete working → full marks
        if grade.score < grade.full_score:
            _log.info("Q%s: is_correct=True but score=%.1f/%.1f → setting score to full_score",
                       question.question_number, grade.score, grade.full_score)
            grade.score = grade.full_score
    elif not grade.is_correct and grade.score >= grade.full_score:
        # Incorrect but full marks → cap at partial
        _log.info("Q%s: is_correct=False but score=%.1f/%.1f → capping",
                   question.question_number, grade.score, grade.full_score)
        grade.score = min(grade.score, grade.full_score * 0.5)

    # 3. Hard cap: score 永远不得超过 full_score，防止得分率 > 1
    if grade.score > grade.full_score:
        _log.warning("Q%s: score=%.1f > full_score=%.1f → clamping",
                     question.question_number, grade.score, grade.full_score)
        grade.score = grade.full_score
    if grade.score < 0:
        grade.score = 0.0

    _log.info("Q%s grading LLM done (total: %.1fs)", question.question_number, _time.monotonic() - _t_start)

    if skip_verification:
        _log.info("Q%s skip_verification=True, returning raw grade", question.question_number)
        return grade

    # --- SymPy 验证 + Confidence 校准 ---
    grade = verify_and_calibrate(grade, question, q_type, stat_client=client)

    _log.info("Q%s total grade_question: %.1fs", question.question_number, _time.monotonic() - _t_start)
    return grade
