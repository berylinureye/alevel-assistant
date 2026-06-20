"""
多 Agent 并行批改核心编排 — 5-agent early-return voting.

流程：
  1. 并行发射 N 个 agent（3 fast + 2 accurate）
  2. as_completed 监听返回；每到 1 个就检查是否能提前结束
     - 若已达成 EARLY_RETURN_MIN_AGENTS 个一致（is_correct + 分数 ±tolerance）→ 立即投票返回
  3. 未触发早返回则等齐/超时，按常规投票
  4. Confidence 调整 + SymPy 验证（一次）
"""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

from models.schemas import GradeResult, QuestionData, QuestionType
from router.models import ModelClient, TaskType
from grader.grader import grade_question, verify_and_calibrate
from grader.multi_agent_config import (
    AGENT_MAX_RETRIES,
    AGENT_TIMEOUT_SECONDS,
    AGENT_TIERS,
    CONFIDENCE_ADJUSTMENTS,
    EARLY_RETURN_ENABLED,
    EARLY_RETURN_MIN_AGENTS,
    EARLY_RETURN_SCORE_TOLERANCE,
    LOW_CONFIDENCE_THRESHOLD,
    SCORE_VARIANCE_PENALTY,
    SCORE_VARIANCE_PENALTY_THRESHOLD,
    SCORE_VARIANCE_THRESHOLD,
    TOTAL_GRADING_TIMEOUT,
)

_log = logging.getLogger("multi_agent")


class GradingError(Exception):
    pass


# ---------------------------------------------------------------------------
# 3.1 单 Agent 调用（带重试，超时不重试）
# ---------------------------------------------------------------------------

def _grade_single_agent(
    question: QuestionData,
    client: ModelClient,
    agent_name: str,
    task: TaskType,
    base_grade: GradeResult | None,
    q_type: QuestionType | None = None,
    max_retries: int = AGENT_MAX_RETRIES,
    cancel_event: threading.Event | None = None,
) -> GradeResult:
    """调用单个 agent 批改。API 错误重试，429 限流特殊处理（指数退避）。
    cancel_event 被 set 时立即放弃后续重试（用于早返回后避免 orphan retry 浪费 API）。"""
    last_error: Exception | None = None
    total_attempts = max_retries + 1 + 2  # 正常重试 + 429 退避重试
    backoff = 3.0

    for attempt in range(total_attempts):
        if cancel_event is not None and cancel_event.is_set():
            raise RuntimeError(f"Agent {agent_name} cancelled (early-return)")
        try:
            return grade_question(
                question, client, task=task,
                base_grade=base_grade, skip_verification=True,
                q_type=q_type,
            )
        except TimeoutError:
            raise
        except Exception as e:
            last_error = e
            err_str = str(e)
            is_rate_limit = "429" in err_str or "rate" in err_str.lower()

            _log.warning(
                "Agent %s attempt %d failed%s: %s",
                agent_name, attempt + 1,
                " (rate-limited)" if is_rate_limit else "",
                e,
            )

            if cancel_event is not None and cancel_event.is_set():
                raise RuntimeError(f"Agent {agent_name} cancelled (early-return)")

            if is_rate_limit and attempt < total_attempts - 1:
                wait = backoff * (1.5 ** attempt)
                _log.info("Agent %s: rate-limited, waiting %.1fs before retry", agent_name, wait)
                # 分段 sleep 以便快速响应 cancel
                waited = 0.0
                while waited < wait:
                    if cancel_event is not None and cancel_event.is_set():
                        raise RuntimeError(f"Agent {agent_name} cancelled (early-return)")
                    time.sleep(min(0.5, wait - waited))
                    waited += 0.5
                continue
            elif not is_rate_limit and attempt < max_retries:
                time.sleep(1)
                continue
            else:
                break

    raise last_error  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 3.2 Early-return 一致性检查
# ---------------------------------------------------------------------------

def _check_early_return(
    results: list[tuple[str, GradeResult]],
) -> tuple[GradeResult, str, str] | None:
    """
    在已返回的 agent 结果中查找一个至少 EARLY_RETURN_MIN_AGENTS 个一致的子集。
    一致定义：is_correct 相同 且 分数差 ≤ EARLY_RETURN_SCORE_TOLERANCE

    返回：命中则返回 (consensus, "early_return", agreement_str)，否则 None
    """
    if len(results) < EARLY_RETURN_MIN_AGENTS:
        return None

    # 按 is_correct 分组
    correct_group = [(n, g) for n, g in results if g.is_correct]
    incorrect_group = [(n, g) for n, g in results if not g.is_correct]

    for group in (correct_group, incorrect_group):
        if len(group) < EARLY_RETURN_MIN_AGENTS:
            continue
        # 检查分数是否都在 tolerance 内（尝试找 min_agents 个分数相近的子集）
        scores = sorted([g.score for _, g in group])
        # 滑动窗口：找连续 N 个分数 max-min ≤ tolerance
        for i in range(len(scores) - EARLY_RETURN_MIN_AGENTS + 1):
            window = scores[i : i + EARLY_RETURN_MIN_AGENTS]
            if window[-1] - window[0] <= EARLY_RETURN_SCORE_TOLERANCE:
                # 命中：从 group 中挑选 score 在 window 范围内的前 N 个
                target_min, target_max = window[0], window[-1]
                aligned = [
                    (n, g) for n, g in group
                    if target_min <= g.score <= target_max
                ]
                aligned = aligned[:EARLY_RETURN_MIN_AGENTS]
                consensus, _, _ = grade_vote([g for _, g in aligned])
                agreement_str = f"{len(aligned)}/{len(results)}(early)"
                return consensus, "early_return", agreement_str
    return None


# ---------------------------------------------------------------------------
# 3.3 投票逻辑（完整投票，N 个 agent 全到齐时使用）
# ---------------------------------------------------------------------------

def grade_vote(
    results: list[GradeResult],
) -> tuple[GradeResult, str, str]:
    """
    投票产生共识结果。

    Returns:
        (consensus_grade, method, agreement_str)
        method: "unanimous" / "majority" / "needs_review"
        agreement_str: "3/3" / "2/3" / "1/2" etc.
    """
    n = len(results)

    # Step 1: is_correct 投票
    correct_votes = [r for r in results if r.is_correct]
    incorrect_votes = [r for r in results if not r.is_correct]

    if len(correct_votes) > len(incorrect_votes):
        winning_side = correct_votes
        is_correct = True
    elif len(incorrect_votes) > len(correct_votes):
        winning_side = incorrect_votes
        is_correct = False
    else:
        # 平票：保守判错，标记审核
        winning_side = incorrect_votes if incorrect_votes else correct_votes
        is_correct = False

    # Step 2: 分数处理（仅用胜出方的分数）
    winning_scores = sorted([r.score for r in winning_side])
    all_scores = sorted([r.score for r in results])
    score_variance = max(all_scores) - min(all_scores) if len(all_scores) > 1 else 0.0

    if len(winning_scores) == 0:
        final_score = 0.0
    elif score_variance <= SCORE_VARIANCE_THRESHOLD:
        final_score = winning_scores[len(winning_scores) // 2]
    else:
        best = max(winning_side, key=lambda r: len(r.short_feedback or ""))
        final_score = best.score

    # Step 3: 从胜出方中选 feedback 最详细的
    best_feedback_result = max(
        winning_side,
        key=lambda r: len(r.short_feedback or "") + len(r.student_feedback or "") + len(r.teacher_feedback or ""),
    )

    # Step 4: 确定一致性
    agreement_count = len(winning_side)
    agreement_str = f"{agreement_count}/{n}"

    if agreement_count == n:
        method = "unanimous"
    elif agreement_count > n // 2:
        method = "majority"
    else:
        method = "needs_review"

    # Step 5: 构造共识 GradeResult
    full_score = best_feedback_result.full_score

    # Enforce is_correct ↔ score consistency
    if is_correct and final_score < full_score:
        final_score = full_score
    elif not is_correct and final_score >= full_score:
        final_score = min(final_score, full_score * 0.5)

    consensus = GradeResult(
        question_number=best_feedback_result.question_number,
        question_type=best_feedback_result.question_type,
        is_correct=is_correct,
        score=final_score,
        full_score=full_score,
        error_type=best_feedback_result.error_type if not is_correct else "correct",
        knowledge_tags=best_feedback_result.knowledge_tags,
        needs_review=(method == "needs_review"),
        short_feedback=best_feedback_result.short_feedback,
        grading_confidence=best_feedback_result.grading_confidence,
        correct_answer=best_feedback_result.correct_answer,
        student_feedback=best_feedback_result.student_feedback,
        teacher_feedback=best_feedback_result.teacher_feedback,
        syllabus_topics=best_feedback_result.syllabus_topics,
        relevant_formulas=best_feedback_result.relevant_formulas,
        unanswered=best_feedback_result.unanswered,
    )

    return consensus, method, agreement_str


# ---------------------------------------------------------------------------
# 3.4 Confidence 调整
# ---------------------------------------------------------------------------

def adjust_confidence(
    grade: GradeResult,
    method: str,
    score_variance: float,
) -> GradeResult:
    adj = CONFIDENCE_ADJUSTMENTS.get(method, 0.0)

    if score_variance > SCORE_VARIANCE_PENALTY_THRESHOLD:
        adj += SCORE_VARIANCE_PENALTY

    grade.grading_confidence = min(1.0, max(0.0, grade.grading_confidence + adj))

    if grade.grading_confidence < LOW_CONFIDENCE_THRESHOLD:
        grade.needs_review = True

    return grade


# ---------------------------------------------------------------------------
# 3.5 核心编排：5-agent early-return
# ---------------------------------------------------------------------------

def grade_question_multi_agent(
    question: QuestionData,
    agent_clients: list[tuple[str, ModelClient]],
    task: TaskType = TaskType.grade,
    base_grade: GradeResult | None = None,
    progress_callback: Callable[[dict], None] | None = None,
) -> GradeResult:
    """
    并行调用多个 agent 批改 → early-return 投票 → confidence 调整 → SymPy 验证。

    5-agent early-return 策略：
    - 全部并行发射
    - 每收到一个返回检查能否提前结束（3 个一致即出）
    - 未触发早返回则等齐或 TOTAL_GRADING_TIMEOUT 超时
    - 未返回的 agent 结果被丢弃（API 请求已发出，资源浪费但值得）
    """
    t_start = time.monotonic()
    results: list[tuple[str, GradeResult]] = []
    early_consensus: tuple[GradeResult, str, str] | None = None
    cancel_event = threading.Event()

    def _notify(data: dict) -> None:
        if progress_callback:
            try:
                progress_callback(data)
            except Exception:
                pass

    def _notify_step(
        *,
        step_type: str,
        title: str,
        summary: str,
        status: str = "running",
        agent_name: str | None = None,
        tool: str | None = None,
        detail: dict | None = None,
    ) -> None:
        """Emit a structured, UI-safe execution step.

        This is intentionally a summary of the workflow state, not raw model
        chain-of-thought. The frontend can render it as a ReAct-like timeline
        without exposing private reasoning text.
        """
        _notify({
            "event": "agent_step",
            "step_type": step_type,
            "title": title,
            "summary": summary,
            "status": status,
            "agent_name": agent_name,
            "tool": tool,
            "detail": detail or {},
        })

    # ---- 预分类（只跑一次）----
    from grader.classifier import classify_question
    # 选 fast tier 做预分类，最快
    fast_clients = [c for n, c in agent_clients if AGENT_TIERS.get(n) == "fast"]
    classify_client = fast_clients[0] if fast_clients else agent_clients[0][1]
    _classify_text = question.question_text
    if question.parent_stem:
        _classify_text = f"{question.parent_stem}\n\n{_classify_text}"
    q_type = classify_question(_classify_text, classify_client)
    _log.info("Q%s pre-classify: %s", question.question_number, q_type.value)
    _notify_step(
        step_type="observe",
        title="题型判断",
        summary=f"识别为 {q_type.value}，后续批改会按该题型选择校验方式。",
        status="completed",
        tool="classify_question",
        detail={"question_type": q_type.value},
    )

    # ---- 并行发射所有 agent ----
    executor = ThreadPoolExecutor(max_workers=len(agent_clients))
    try:
        future_to_agent = {}
        for agent_name, client in agent_clients:
            future = executor.submit(
                _grade_single_agent, question, client, agent_name, task, base_grade,
                q_type=q_type, cancel_event=cancel_event,
            )
            future_to_agent[future] = agent_name
            tier = AGENT_TIERS.get(agent_name, "unknown")
            _notify({"agent_name": agent_name, "tier": tier, "model_id": getattr(client, "model_id", ""), "status": "started"})
            _notify_step(
                step_type="act",
                title=f"{agent_name} 开始批改",
                summary="并行调用一个独立模型判断学生答案、分数和错误类型。",
                status="running",
                agent_name=agent_name,
                tool="grade_question",
                detail={
                    "tier": tier,
                    "model_id": getattr(client, "model_id", ""),
                },
            )

        # 逐个接收，动态检查 early-return
        # 捕获 as_completed 的整体 timeout，以便用已收到的部分结果继续投票
        try:
            completed_iter = as_completed(future_to_agent, timeout=TOTAL_GRADING_TIMEOUT)
            _iter_timed_out = False
        except TimeoutError:
            completed_iter = iter(())
            _iter_timed_out = True

        try:
            for future in completed_iter:
                agent_name = future_to_agent[future]
                t_agent = time.monotonic()
                try:
                    grade_result = future.result(timeout=AGENT_TIMEOUT_SECONDS)
                    results.append((agent_name, grade_result))
                    _notify({
                        "agent_name": agent_name,
                        "status": "completed",
                        "is_correct": grade_result.is_correct,
                        "score": grade_result.score,
                        "elapsed": round(t_agent - t_start, 1),
                    })
                    _notify_step(
                        step_type="observe",
                        title=f"{agent_name} 返回结果",
                        summary=f"判断为{'正确' if grade_result.is_correct else '需要订正'}，得分 {grade_result.score}/{grade_result.full_score}。",
                        status="completed",
                        agent_name=agent_name,
                        detail={
                            "is_correct": grade_result.is_correct,
                            "score": grade_result.score,
                            "full_score": grade_result.full_score,
                            "elapsed": round(t_agent - t_start, 1),
                        },
                    )
                    _log.info(
                        "Q%s agent %s completed: is_correct=%s score=%.1f (%.1fs, total_returned=%d)",
                        question.question_number, agent_name,
                        grade_result.is_correct, grade_result.score,
                        t_agent - t_start, len(results),
                    )

                    # Early-return 检查
                    if EARLY_RETURN_ENABLED:
                        ec = _check_early_return(results)
                        if ec is not None:
                            early_consensus = ec
                            _log.info(
                                "Q%s EARLY-RETURN triggered after %d agents (%.1fs): %s",
                                question.question_number, len(results),
                                t_agent - t_start, ec[2],
                            )
                            _notify_step(
                                step_type="decide",
                                title="提前达成一致",
                                summary=f"已有 {ec[2]} 的模型结果足够一致，停止等待剩余模型。",
                                status="completed",
                                detail={"agreement": ec[2], "returned_agents": len(results)},
                            )
                            cancel_event.set()  # 通知其他 agent 停止
                            break
                except TimeoutError:
                    _notify({"agent_name": agent_name, "status": "timeout"})
                    _notify_step(
                        step_type="observe",
                        title=f"{agent_name} 超时",
                        summary="该模型未在限定时间内返回，本题会使用已返回结果继续投票。",
                        status="failed",
                        agent_name=agent_name,
                    )
                    _log.warning("Q%s agent %s timed out", question.question_number, agent_name)
                except Exception as e:
                    _notify({"agent_name": agent_name, "status": "failed", "error": str(e)})
                    _notify_step(
                        step_type="observe",
                        title=f"{agent_name} 失败",
                        summary="该模型调用失败，本题会使用其他模型结果继续判断。",
                        status="failed",
                        agent_name=agent_name,
                        detail={"error": str(e)[:300]},
                    )
                    _log.warning("Q%s agent %s failed: %s", question.question_number, agent_name, e)
        except TimeoutError:
            # as_completed 的整体 timeout：用已收到的结果继续投票
            _log.warning(
                "Q%s total timeout (%.0fs) reached with %d/%d agents returned — voting with partial results",
                question.question_number, TOTAL_GRADING_TIMEOUT, len(results), len(agent_clients),
            )
            cancel_event.set()

        if _iter_timed_out:
            _log.warning(
                "Q%s: as_completed timed out immediately (%d results)",
                question.question_number, len(results),
            )
            cancel_event.set()
    finally:
        # 不等待剩余 future，立即退出（它们会在后台继续但结果丢弃）
        executor.shutdown(wait=False, cancel_futures=True)

    # ---- 降级策略 ----
    if len(results) == 0:
        raise GradingError(f"Q{question.question_number}: 所有 agent 均超时或失败，无法完成批改")

    if len(results) == 1:
        agent_name, single = results[0]
        _log.warning(
            "Q%s only 1 agent returned (%s), degrading confidence",
            question.question_number, agent_name,
        )
        single.grading_confidence = max(0.0, single.grading_confidence - 0.3)
        single.needs_review = True
        return verify_and_calibrate(single, question, single.question_type, stat_client=classify_client)

    # ---- 投票（early-return 或常规）----
    if early_consensus is not None:
        consensus, method, agreement = early_consensus
    else:
        grade_results = [r for _, r in results]
        consensus, method, agreement = grade_vote(grade_results)

    all_scores = sorted([r.score for _, r in results])
    score_variance = max(all_scores) - min(all_scores) if len(all_scores) > 1 else 0.0

    _log.info(
        "Q%s vote: method=%s agreement=%s scores=%s variance=%.1f",
        question.question_number, method, agreement, all_scores, score_variance,
    )

    _notify({
        "question_number": question.question_number,
        "status": "vote_complete",
        "method": method,
        "agreement": agreement,
    })
    _notify_step(
        step_type="decide",
        title="投票完成",
        summary=f"采用 {method} 策略，模型一致度 {agreement}，分数波动 {score_variance:.1f}。",
        status="completed",
        detail={
            "method": method,
            "agreement": agreement,
            "scores": all_scores,
            "score_variance": score_variance,
        },
    )

    # ---- Confidence 调整 ----
    consensus = adjust_confidence(consensus, method, score_variance)

    # ---- SymPy + 数值验证（仅一次）----
    consensus = verify_and_calibrate(consensus, question, consensus.question_type, stat_client=classify_client)
    _notify_step(
        step_type="observe",
        title="校验完成",
        summary=f"最终置信度 {consensus.grading_confidence:.2f}，{'需要人工复核' if consensus.needs_review else '无需人工复核'}。",
        status="completed",
        tool="verify_and_calibrate",
        detail={
            "grading_confidence": consensus.grading_confidence,
            "needs_review": consensus.needs_review,
        },
    )

    # ---- 把各 agent 的推理素材挂到 consensus 上，供「解题思路聚合器」复用 ----
    # 这些是 5 份独立解题推理，aggregator 就是要把它们压成一份标准格式的解题思路。
    try:
        consensus._agent_deliberations = [
            {
                "agent": name,
                "is_correct": g.is_correct,
                "score": g.score,
                "correct_answer": g.correct_answer,
                "short_feedback": g.short_feedback,
                "student_feedback": g.student_feedback,
                "error_type": g.error_type,
                "relevant_formulas": list(g.relevant_formulas or []),
            }
            for name, g in results
        ]
    except Exception as _delib_err:
        _log.debug("failed to attach deliberations: %s", _delib_err)

    _log.info(
        "Q%s multi-agent done: is_correct=%s score=%.1f conf=%.2f (%.1fs, %d/%d agents, method=%s)",
        question.question_number, consensus.is_correct, consensus.score,
        consensus.grading_confidence, time.monotonic() - t_start,
        len(results), len(agent_clients), method,
    )

    return consensus
