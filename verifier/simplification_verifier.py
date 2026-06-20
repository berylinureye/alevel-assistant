"""
Deterministic post-check: scan student_answer for fractions a/b that are NOT in
lowest terms, and surface them so the grader can flag presentation issues
without needing an LLM call.

Rationale: A-Level mark schemes often deduct a "presentation" mark when a correct
value is left unsimplified (e.g. student writes "24/210" instead of "4/35").
Asking the grading LLM to detect this costs extra tokens and is unreliable on
long probability tables. A two-line gcd check is faster and never missed.

Public API:
    check_simplification(text) -> SimplificationResult
    apply_simplification_check(grade, question) -> None   # mutates grade in-place
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from math import gcd


# Match a/b only when both sides are positive integers and b > 1 (b=1 is trivially
# already simplest). Exclude LaTeX \frac which gets normalized separately.
_FRAC_RE = re.compile(r"(?<![\w\\\d.])(\d{1,5})\s*/\s*(\d{2,5})(?!\d)")

# \frac{a}{b} — also capture
_LATEX_FRAC_RE = re.compile(r"\\(?:d?frac|tfrac)\s*\{\s*(\d{1,5})\s*\}\s*\{\s*(\d{2,5})\s*\}")


@dataclass
class SimplificationResult:
    # list of (original "a/b", simplified "a'/b'") in first-seen order
    unsimplified: list[tuple[str, str]] = field(default_factory=list)

    @property
    def has_issues(self) -> bool:
        return len(self.unsimplified) > 0

    def feedback_sentence(self) -> str:
        """One-line Chinese summary, safe to append to short_feedback."""
        if not self.unsimplified:
            return ""
        parts = [f"{orig} 应化简为 {simp}" for orig, simp in self.unsimplified]
        return "分数未化简：" + "；".join(parts) + "。"


def _collect_fractions(text: str) -> list[tuple[int, int, str]]:
    """Yield (num, den, literal) for every a/b and \\frac{a}{b} in text."""
    out: list[tuple[int, int, str]] = []
    for m in _FRAC_RE.finditer(text):
        a, b = int(m.group(1)), int(m.group(2))
        out.append((a, b, f"{a}/{b}"))
    for m in _LATEX_FRAC_RE.finditer(text):
        a, b = int(m.group(1)), int(m.group(2))
        out.append((a, b, f"{a}/{b}"))
    return out


def check_simplification(text: str | None) -> SimplificationResult:
    """Return a list of (unsimplified, simplified) pairs found in text.

    Rules:
    - Only integer fractions like 24/210 or \\frac{24}{210}.
    - gcd(num, den) > 1 → unsimplified.
    - Deduplicate by original literal (same "24/210" appearing twice → one entry).
    - A fraction appearing multiple times in the same table is still listed once.
    """
    if not text:
        return SimplificationResult()

    seen: set[str] = set()
    unsimp: list[tuple[str, str]] = []
    for num, den, literal in _collect_fractions(text):
        if num == 0 or den <= 1:
            continue
        g = gcd(num, den)
        if g <= 1:
            continue
        if literal in seen:
            continue
        seen.add(literal)
        unsimp.append((literal, f"{num // g}/{den // g}"))
    return SimplificationResult(unsimplified=unsimp)


def apply_simplification_check(grade, question) -> bool:
    """Inspect question.student_answer for unsimplified fractions. If any are
    found AND the grade is currently marked correct, attach a feedback note and
    optionally deduct a single presentation mark.

    Mutates `grade` in place. Returns True if any issue was flagged.

    Policy:
    - Only acts when grade.is_correct is True — unsimplified doesn't make an
      already-wrong answer more wrong.
    - Full score ≥ 3: deduct 1 presentation mark (cap at >= 1.0 so student still
      gets method credit). Full score ≤ 2: keep score, just note.
    - Appends a short Chinese sentence to short_feedback / student_feedback.
    - Leaves correct_answer untouched (upstream verifiers manage that field).
    """
    if not grade.is_correct:
        return False
    text = getattr(question, "student_answer", "") or ""
    # Also look at the last working step in case final answer lives there
    working = getattr(question, "working_steps", []) or []
    if working:
        text = text + "\n" + str(working[-1])

    res = check_simplification(text)
    if not res.has_issues:
        return False

    note = res.feedback_sentence()
    # Short feedback: append only if not already there
    existing_sf = (grade.short_feedback or "").strip()
    if note not in existing_sf:
        grade.short_feedback = (existing_sf + " " + note).strip() if existing_sf else note

    # Student feedback (plain text)
    existing_stu = (grade.student_feedback or "").strip()
    stu_note = note
    if existing_stu and stu_note not in existing_stu:
        grade.student_feedback = existing_stu + "\n" + stu_note
    elif not existing_stu:
        grade.student_feedback = stu_note

    # Deduct 1 presentation mark when the question is worth ≥ 3 marks
    lost = 0.0
    try:
        full = float(grade.full_score or 0)
        cur = float(grade.score or 0)
    except (TypeError, ValueError):
        full, cur = 0.0, 0.0
    if full >= 3 and cur >= full:  # only deduct if student had full marks
        new_score = max(1.0, full - 1.0)
        if new_score < cur:
            lost = cur - new_score
            grade.score = new_score
            # Presentation issue → needs_review so teacher can confirm
            grade.needs_review = True

    # Record the detail-deduction tag so the UI can show it as a pill,
    # even when lost=0 (e.g. 1-mark questions keep full score but still get flagged).
    deductions = getattr(grade, "detail_deductions", None)
    if deductions is None:
        try:
            grade.detail_deductions = []
            deductions = grade.detail_deductions
        except Exception:
            deductions = None
    if deductions is not None:
        examples = "、".join(f"{o}→{s}" for o, s in res.unsimplified[:3])
        if len(res.unsimplified) > 3:
            examples += "…"
        deductions.append({
            "tag": "分数未化简",
            "detail": f"分数未化简：{examples}",
            "lost_points": lost,
        })

    return True
