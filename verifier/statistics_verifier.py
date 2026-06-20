"""
Statistics verifier — deterministic numeric check for A-Level statistics questions.

Motivation: the LLM grader often mis-arithmetics multi-step statistics problems
(combined mean/SD, grouped-data mean, quartiles) and invents a wrong
"correct_answer", then penalises a correct student answer. This module uses a
small LLM call ONLY to extract structured data from the question, and Python to
compute the answer deterministically.

Public API:
    verify_statistics(question_text, student_answer, working_steps, client) -> StatsVerification

The returned object tells the caller whether the student's numeric answer
matches ANY deterministically-computed acceptable answer (multiple conventions
are tried for quartiles).
"""
from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass, field
from typing import Any

from router.models import ModelClient, ModelRequest, TaskType
from utils.json_repair import parse_json_object

_log = logging.getLogger("verifier.statistics")


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class StatsVerification:
    verified: bool                       # we produced a deterministic answer set
    student_matches: bool | None         # student's numeric answer matches ANY acceptable answer
    acceptable_answers: list[float] = field(default_factory=list)
    primary_answer: str | None = None    # the canonical correct answer (exact form if possible)
    detail: str = ""


# ---------------------------------------------------------------------------
# Extractor prompt (narrow, reliable task — just extract structured data)
# ---------------------------------------------------------------------------

_EXTRACTOR_PROMPT = r"""You extract structured numerical data from an A-Level statistics question.

DO NOT solve the problem. DO NOT grade. Only describe the data present in the QUESTION itself.

IMPORTANT: Fill EVERY numeric field mentioned in the question text. If the question says "∑y = 910 and ∑y² = 42 850", those go into sum_x and sum_x_sq for that group. If it says "mean age is 15.5 years and the standard deviation is 1.2 years", those go into mean and sd. Do NOT omit fields that the question provides.

Return ONE JSON object matching exactly this schema:

{
  "pattern": "<one of: combined_summary, grouped_table, raw_list, summary_stats, none>",
  "target": "<one of: mean, standard_deviation, variance, median, q1, q3, iqr, mid_interval, none>",

  // for pattern=combined_summary (e.g. two groups, one given as n/mean/sd, one as n/Σy/Σy²):
  "group_a": {"n": <int>, "mean": <float|null>, "sd": <float|null>, "sum_x": <float|null>, "sum_x_sq": <float|null>},
  "group_b": {"n": <int>, "mean": <float|null>, "sd": <float|null>, "sum_x": <float|null>, "sum_x_sq": <float|null>},

  // for pattern=grouped_table (frequency distribution with class intervals):
  "classes": [{"lo": <float>, "hi": <float>, "freq": <int>}, ...],

  // for pattern=raw_list (raw numeric data):
  "data": [<float>, ...],

  // for pattern=summary_stats (single set, given as n/Σx/Σx² OR n/mean/sd):
  "summary": {"n": <int>, "mean": <float|null>, "sd": <float|null>, "sum_x": <float|null>, "sum_x_sq": <float|null>},

  // for mid_interval target ("state the mid-interval value of the first interval"):
  "first_interval": {"lo": <float>, "hi": <float>}
}

Rules:
- "n" for SD/variance computations refers to what appears in the question; A-Level typically uses the population formula σ² = Σx²/n − x̄² (not the /(n−1) sample formula) unless explicitly stated.
- For raw_list, include ALL data points in the ORIGINAL order.
- For grouped_table, write intervals as lo and hi (e.g. "15 ≤ x < 30" → lo=15, hi=30). For "31-35" style, use lo=31, hi=35 — the caller will handle continuous vs discrete mid-point adjustment based on the "cb" flag below.
- Also include a "class_boundaries" flag: "continuous" (e.g. 15 ≤ x < 30, midpoint=(15+30)/2) OR "discrete" (e.g. 31–35 books, continuous boundaries 30.5–35.5, midpoint 33). Output under top-level key "cb". Default "continuous" unless the data is integer counts (books, shelves, people).
- Only fill fields that apply to the detected pattern; leave the rest null or omit.
- If the question does not fit any pattern, return {"pattern":"none","target":"none"}.
- DATA SELECTION: the PARENT STEM often contains the raw data (a table, a list, or summary statistics) that the SUB-QUESTION refers to. Always look in BOTH the parent stem and the sub-question text for numeric data. When the stem contains multiple groups (e.g. "Gulls: …" and "Herons: …"), pick ONLY the group the sub-question asks about — do NOT mix or concatenate unrelated groups.
- If the question asks for several statistics at once (e.g. "find the median and the interquartile range"), pick a SINGLE most-specific target in this priority: iqr > q3 > q1 > standard_deviation > variance > median > mean > mid_interval. The caller will deterministically compute the other statistics from the same extracted data.

PARENT STEM (shared setup; may contain the data table/list):
{parent_stem}

SUB-QUESTION:
{question_text}

STUDENT'S WORKING (may help you disambiguate the data):
{working_steps}

OUTPUT JSON ONLY, NO MARKDOWN:"""


# ---------------------------------------------------------------------------
# Deterministic computations
# ---------------------------------------------------------------------------

def _population_variance(n: int, sum_x: float, sum_x_sq: float) -> float:
    mean = sum_x / n
    return sum_x_sq / n - mean * mean


def _combined_mean_sd(group_a: dict, group_b: dict) -> tuple[float, float]:
    """Combined mean & SD for two groups. Each group must resolve to (n, Σx, Σx²)."""
    def _resolve(g: dict) -> tuple[int, float, float]:
        n = int(g["n"])
        if g.get("sum_x") is not None and g.get("sum_x_sq") is not None:
            return n, float(g["sum_x"]), float(g["sum_x_sq"])
        mean = g.get("mean")
        sd = g.get("sd")
        if mean is None or sd is None:
            raise ValueError("group missing either (sum_x, sum_x_sq) or (mean, sd)")
        sum_x = float(mean) * n
        # Σx² = n(σ² + μ²)
        sum_x_sq = n * (float(sd) ** 2 + float(mean) ** 2)
        return n, sum_x, sum_x_sq

    n_a, sx_a, sx2_a = _resolve(group_a)
    n_b, sx_b, sx2_b = _resolve(group_b)
    n = n_a + n_b
    sx = sx_a + sx_b
    sx2 = sx2_a + sx2_b
    mean = sx / n
    var = sx2 / n - mean * mean
    sd = math.sqrt(max(0.0, var))
    return mean, sd


def _grouped_mean_sd(classes: list[dict], cb: str = "continuous") -> tuple[float, float]:
    # For discrete (e.g. "31–35"), true class boundaries are lo−0.5 and hi+0.5,
    # midpoint = (lo + hi)/2 (unchanged), so arithmetic is the same either way.
    # We keep the cb flag for future-proofing.
    total_f = 0
    sum_fx = 0.0
    sum_fx2 = 0.0
    for c in classes:
        mid = (float(c["lo"]) + float(c["hi"])) / 2.0
        f = int(c["freq"])
        total_f += f
        sum_fx += f * mid
        sum_fx2 += f * mid * mid
    if total_f == 0:
        raise ValueError("total frequency is zero")
    mean = sum_fx / total_f
    var = sum_fx2 / total_f - mean * mean
    sd = math.sqrt(max(0.0, var))
    return mean, sd


def _summary_mean_sd(s: dict) -> tuple[float, float]:
    n = int(s["n"])
    if s.get("sum_x") is not None and s.get("sum_x_sq") is not None:
        mean = float(s["sum_x"]) / n
        var = float(s["sum_x_sq"]) / n - mean * mean
        return mean, math.sqrt(max(0.0, var))
    if s.get("mean") is not None and s.get("sd") is not None:
        return float(s["mean"]), float(s["sd"])
    raise ValueError("summary missing fields")


def _quartiles_all_conventions(sorted_data: list[float]) -> dict[str, tuple[float, float, float]]:
    """
    Return Q1/Q3/IQR under 4 common A-Level/IGCSE conventions.
    Returns dict { convention_name: (Q1, Q3, IQR) }.
    """
    n = len(sorted_data)
    if n < 4:
        return {}

    out: dict[str, tuple[float, float, float]] = {}

    # Convention A: position = n/4 and 3n/4, take the ceiling-index value
    #               (i.e. "the 3rd value" for n=12: Q1 at index 3 → 3rd value)
    def _at(pos_1idx: float) -> float:
        # linear interpolation between floor and ceil 1-indexed positions
        lo = int(math.floor(pos_1idx))
        hi = int(math.ceil(pos_1idx))
        lo = max(1, min(n, lo))
        hi = max(1, min(n, hi))
        if lo == hi:
            return sorted_data[lo - 1]
        frac = pos_1idx - lo
        return sorted_data[lo - 1] + frac * (sorted_data[hi - 1] - sorted_data[lo - 1])

    # A: Cambridge textbook "3rd, 9th value" (position n/4 rounded up)
    p_a_q1 = n / 4
    p_a_q3 = 3 * n / 4
    q1_a = sorted_data[int(math.ceil(p_a_q1)) - 1]
    q3_a = sorted_data[int(math.ceil(p_a_q3)) - 1]
    out["A_ceil(n/4)"] = (q1_a, q3_a, q3_a - q1_a)

    # B: average of kth and (k+1)th when n is a multiple of 4
    if n % 4 == 0:
        k1 = n // 4
        q1_b = (sorted_data[k1 - 1] + sorted_data[k1]) / 2
        k3 = 3 * n // 4
        q3_b = (sorted_data[k3 - 1] + sorted_data[k3]) / 2
        out["B_avg_at_n/4"] = (q1_b, q3_b, q3_b - q1_b)

    # C: (n+1)/4 position with linear interpolation (Cambridge 9709 formal method)
    q1_c = _at((n + 1) / 4)
    q3_c = _at(3 * (n + 1) / 4)
    out["C_(n+1)/4_interp"] = (q1_c, q3_c, q3_c - q1_c)

    # D: Tukey hinges (median of lower half / median of upper half)
    half = n // 2
    lower = sorted_data[:half]
    upper = sorted_data[n - half:]

    def _median(xs: list[float]) -> float:
        m = len(xs)
        if m == 0:
            return 0.0
        if m % 2 == 1:
            return xs[m // 2]
        return (xs[m // 2 - 1] + xs[m // 2]) / 2

    q1_d = _median(lower)
    q3_d = _median(upper)
    out["D_tukey_hinges"] = (q1_d, q3_d, q3_d - q1_d)

    return out


def _median_of(sorted_data: list[float]) -> float:
    n = len(sorted_data)
    if n == 0:
        return 0.0
    if n % 2 == 1:
        return sorted_data[n // 2]
    return (sorted_data[n // 2 - 1] + sorted_data[n // 2]) / 2


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _extract_numeric(s: str | None) -> float | None:
    """Extract the last-looking numeric value from a string (student's final answer)."""
    if not s:
        return None
    # strip LaTeX wrappers
    s = s.replace("\\approx", "").replace("≈", "").strip()
    # \frac{a}{b} → a/b
    s = re.sub(r"\\frac\s*\{(-?\d+(?:\.\d+)?)\}\s*\{(-?\d+(?:\.\d+)?)\}",
               lambda m: f"{m.group(1)}/{m.group(2)}", s)
    # try a/b fraction first (rightmost), as A-Level often writes exact fractions
    frac_m = None
    for fm in re.finditer(r"(-?\d+(?:\.\d+)?)\s*/\s*(-?\d+(?:\.\d+)?)", s):
        frac_m = fm
    # try the rightmost plain number
    matches = list(_NUMBER_RE.finditer(s))
    if not matches and not frac_m:
        return None
    if frac_m:
        try:
            a = float(frac_m.group(1))
            b = float(frac_m.group(2))
            if b != 0:
                return a / b
        except ValueError:
            pass
    if matches:
        try:
            return float(matches[-1].group(0))
        except ValueError:
            return None
    return None


def _close(a: float, b: float, rel_tol: float = 0.01, abs_tol: float = 0.02) -> bool:
    """A-Level rounding is often to 3 sig figs; allow ~1% relative tolerance."""
    return math.isclose(a, b, rel_tol=rel_tol, abs_tol=abs_tol)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def _extract(
    question_text: str,
    parent_stem: str | None,
    working_steps: list[str],
    client: ModelClient,
) -> dict | None:
    """One LLM call, narrow task: extract structured data. Returns None on failure."""
    prompt = _EXTRACTOR_PROMPT.replace(
        "{question_text}", question_text or "(empty)",
    ).replace(
        "{parent_stem}", parent_stem or "(none)",
    ).replace(
        "{working_steps}", "\n".join(working_steps) if working_steps else "(none)",
    )
    try:
        raw = client.call(ModelRequest(task=TaskType.grade, prompt=prompt, max_tokens=1024, temperature=0.0))
        data = parse_json_object(raw)
        _log.debug("statistics extractor output: %s", json.dumps(data, ensure_ascii=False, default=str)[:500])
        return data
    except Exception as e:
        _log.warning("statistics extractor failed: %s", e)
        return None


def verify_statistics(
    question_text: str,
    student_answer: str | None,
    working_steps: list[str],
    client: ModelClient,
    parent_stem: str | None = None,
) -> StatsVerification:
    """Main entry. Returns verification result with acceptable answer set."""
    data = _extract(question_text, parent_stem, working_steps, client)
    if not data:
        return StatsVerification(verified=False, student_matches=None, detail="extractor failed")
    _log.info("stat-extractor output: %s", json.dumps(data, ensure_ascii=False, default=str)[:400])

    pattern = (data.get("pattern") or "none").strip()
    target = (data.get("target") or "none").strip()
    if pattern == "none" or target == "none":
        return StatsVerification(verified=False, student_matches=None,
                                 detail=f"pattern={pattern} target={target}")

    acceptable: list[float] = []
    primary: str | None = None
    detail_parts: list[str] = [f"pattern={pattern} target={target}"]

    try:
        if pattern == "combined_summary":
            mean, sd = _combined_mean_sd(data["group_a"], data["group_b"])
            var = sd * sd
            if target == "mean":
                acceptable = [mean]
                primary = f"{mean:.6g}"
            elif target == "standard_deviation":
                acceptable = [sd]
                primary = f"{sd:.6g}"
            elif target == "variance":
                acceptable = [var]
                primary = f"{var:.6g}"
            detail_parts.append(f"mean={mean:.4f} sd={sd:.4f}")

        elif pattern == "grouped_table":
            cb = (data.get("cb") or "continuous").strip()
            classes = data.get("classes") or []
            mean, sd = _grouped_mean_sd(classes, cb=cb)
            var = sd * sd
            if target == "mean":
                acceptable = [mean]
                primary = f"{mean:.6g}"
            elif target == "standard_deviation":
                acceptable = [sd]
                primary = f"{sd:.6g}"
            elif target == "variance":
                acceptable = [var]
                primary = f"{var:.6g}"
            elif target == "mid_interval":
                fi = data.get("first_interval") or (classes[0] if classes else None)
                if fi is not None:
                    mid = (float(fi["lo"]) + float(fi["hi"])) / 2.0
                    # discrete convention: "31-35" → mid = (31+35)/2 = 33 (same answer)
                    acceptable = [mid]
                    primary = f"{mid:.6g}"
            detail_parts.append(f"mean={mean:.4f} sd={sd:.4f}")

        elif pattern == "raw_list":
            raw = data.get("data") or []
            values = [float(v) for v in raw]
            values_sorted = sorted(values)
            # Compute the full five-number summary up front so we can report
            # related stats alongside the primary target (e.g. "Median + IQR"
            # questions should show BOTH in correct_answer, not just one).
            med = _median_of(values_sorted) if values_sorted else None
            conventions = _quartiles_all_conventions(values_sorted)
            # Pick the most common A-Level convention (Tukey hinges) as the
            # display canonical; `acceptable` still includes all conventions
            # for matching tolerance.
            q1_display = q3_display = iqr_display = None
            if conventions:
                if "D_tukey_hinges" in conventions:
                    q1_display, q3_display, iqr_display = conventions["D_tukey_hinges"]
                else:
                    q1_display, q3_display, iqr_display = next(iter(conventions.values()))

            def _combined_primary() -> str:
                parts: list[str] = []
                if med is not None:
                    parts.append(f"\\text{{Median}} = {med:.6g}")
                if q1_display is not None:
                    parts.append(f"Q_1 = {q1_display:.6g}")
                if q3_display is not None:
                    parts.append(f"Q_3 = {q3_display:.6g}")
                if iqr_display is not None:
                    parts.append(f"\\text{{IQR}} = {iqr_display:.6g}")
                return ", ".join(parts)

            if target == "median":
                acceptable = [med] if med is not None else []
                primary = _combined_primary()
            elif target in ("q1", "q3", "iqr"):
                uniq: dict[float, str] = {}
                for name, (q1, q3, iqr) in conventions.items():
                    value = {"q1": q1, "q3": q3, "iqr": iqr}[target]
                    if not any(_close(value, k) for k in uniq):
                        uniq[value] = name
                acceptable = list(uniq.keys())
                primary = _combined_primary()
                detail_parts.append(f"conventions={list(uniq.values())}")
            elif target == "mean":
                m = sum(values_sorted) / len(values_sorted) if values_sorted else 0.0
                acceptable = [m]
                primary = f"{m:.6g}"
            elif target == "standard_deviation":
                if values_sorted:
                    n = len(values_sorted)
                    mean = sum(values_sorted) / n
                    var = sum(v * v for v in values_sorted) / n - mean * mean
                    sd = math.sqrt(max(0.0, var))
                    acceptable = [sd]
                    primary = f"{sd:.6g}"

        elif pattern == "summary_stats":
            mean, sd = _summary_mean_sd(data.get("summary") or {})
            var = sd * sd
            if target == "mean":
                acceptable = [mean]
                primary = f"{mean:.6g}"
            elif target == "standard_deviation":
                acceptable = [sd]
                primary = f"{sd:.6g}"
            elif target == "variance":
                acceptable = [var]
                primary = f"{var:.6g}"
            detail_parts.append(f"mean={mean:.4f} sd={sd:.4f}")

    except Exception as e:
        _log.warning("statistics compute failed: %s data=%s", e, json.dumps(data, default=str)[:400])
        return StatsVerification(verified=False, student_matches=None,
                                 detail=f"compute error: {e}")

    if not acceptable:
        return StatsVerification(verified=False, student_matches=None,
                                 detail="no acceptable answer computed; " + "; ".join(detail_parts))

    student_num = _extract_numeric(student_answer)
    if student_num is None:
        match = None
        detail_parts.append("student_answer not numeric")
    else:
        match = any(_close(student_num, v) for v in acceptable)
        detail_parts.append(
            f"student={student_num:.6g} acceptable={[round(v, 6) for v in acceptable]} match={match}"
        )

    # Fallback: if student_answer didn't match but working_steps contains a value that does,
    # the segmenter probably mis-picked an intermediate number as the "final answer".
    # Credit the student for arriving at the right value in their work.
    # NOTE: no working_steps fallback. Rationale: segmenters sometimes narrate their own
    # computations into working_steps (including arriving at the correct answer), which
    # would wrongly credit a student whose actual answer was wrong. Rely on segmenter
    # prompt hardening to correctly extract student_answer.

    return StatsVerification(
        verified=True,
        student_matches=match,
        acceptable_answers=acceptable,
        primary_answer=primary,
        detail="; ".join(detail_parts),
    )
