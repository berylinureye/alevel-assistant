"""
Probability verifier — deterministic check for A-Level discrete-probability questions.

Motivation: LLM agents routinely miscompute conditional-probability questions
like "Find P(X≥2 | at least 1 red AND at least 1 blue)" — the arithmetic is
easy but identifying the right subsets for A, B, A∩B trips the model up.
Pattern: narrow LLM call to EXTRACT the sample space + events, Python computes
the exact fraction.

Public API:
    verify_probability(question_text, parent_stem, student_answer,
                       working_steps, client) -> ProbVerification

Supported patterns:
  * "distribution" — a fully-specified discrete distribution {value: probability}
    plus a target P(A), P(A|B), or P(A∩B) described by value-subsets.
"""
from __future__ import annotations

import ast
import json
import logging
import math
import re
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from router.models import ModelClient, ModelRequest, TaskType
from utils.json_repair import parse_json_object

_log = logging.getLogger("verifier.probability")


@dataclass
class ProbVerification:
    verified: bool
    student_matches: bool | None
    primary_answer: str | None = None
    exact_fraction: str | None = None
    decimal: float | None = None
    detail: str = ""


_EXTRACTOR_PROMPT = r"""You extract structured data from an A-Level probability question. Do NOT solve or grade — only describe the discrete sample space and the events.

You will be given a PARENT STEM (shared setup like "10 marbles, 4 red 6 blue; 4 drawn without replacement; X = number blue") and a SUB-QUESTION (e.g. "Find P(X≥2 | at least 1 red AND at least 1 blue)").

Return EXACTLY this JSON (no markdown):

{
  "pattern": "<one of: distribution, none>",
  "target":  "<one of: P_A, P_A_given_B, P_A_and_B, none>",

  // The full discrete distribution of the random variable(s) referenced.
  // Give each outcome's probability as a rational "num/den" string so there is
  // no rounding loss. Use a consistent denominator when possible.
  "distribution": [
    {"x": <int or float>, "p": "<num>/<den>"}
  ],

  // Subsets of x-values defining events A and B. Leave [] if not applicable.
  "event_A": [<int or float>, ...],
  "event_B": [<int or float>, ...]
}

RULES
- Enumerate EVERY value of X with non-zero probability in "distribution". For hypergeometric draws (choose k from a bag) this means x from max(0, k-non_target) to min(k, target).
- Compute each p using combinatorics, e.g. P(X=k) = C(n_target, k) * C(n_other, draws-k) / C(n_total, draws). Write the FINAL EVALUATED fraction as "num/den" (e.g. "90/210"), NOT the symbolic formula. The caller expects plain integer/integer strings. Use an unsimplified common denominator so probabilities are easy to add (e.g. 1/210, 24/210, 90/210, 80/210, 15/210 — do not pre-simplify).
- Parse compound event descriptions carefully:
    "at least 2 blue"        → A = {x : x ≥ 2}
    "more than 3"            → A = {x : x > 3}
    "at least 1 red AND at least 1 blue" (with X = #blue out of 4 drawn)
                             → exclude X=0 (all red) AND X=4 (all blue)
                             → B = {1, 2, 3}
- target:
    * "P_A"        — question asks P(A) (no conditioning).
    * "P_A_given_B" — question contains "given that" / conditional bar.
    * "P_A_and_B"   — question asks P(A ∩ B) explicitly.
- If the question does NOT reduce to a discrete distribution (e.g. continuous normal-distribution problem, hypothesis test, regression), return {"pattern":"none","target":"none"}.

PARENT STEM:
{parent_stem}

SUB-QUESTION:
{question_text}

STUDENT'S WORKING (may help disambiguate):
{working_steps}

OUTPUT JSON ONLY:"""


_CONDITIONAL_KEYWORDS = (
    "given that",
    "given ",
    "conditional",
    "|",
)
_PROBABILITY_KEYWORDS = (
    "probability",
    "p(x",
    "p(a",
    "p(b",
    "probability distribution",
)


def looks_like_discrete_probability(text: str) -> bool:
    if not text:
        return False
    low = text.lower()
    prob_hit = any(kw in low for kw in _PROBABILITY_KEYWORDS)
    return prob_hit


_COMB_RE = re.compile(
    r"""
    (?:
        C\(\s*(\d+)\s*,\s*(\d+)\s*\)    # C(n, k)
      | (\d+)\s*C\s*(\d+)                # 10C4 or 4C2
      | \\binom\{\s*(\d+)\s*\}\{\s*(\d+)\s*\}  # \binom{n}{k}
    )
    """,
    re.VERBOSE,
)


def _replace_combinations(s: str) -> str:
    """Turn C(n,k) / nCk / \\binom{n}{k} into the integer value."""

    def _sub(m: re.Match) -> str:
        groups = m.groups()
        pair = None
        if groups[0] is not None:
            pair = (int(groups[0]), int(groups[1]))
        elif groups[2] is not None:
            pair = (int(groups[2]), int(groups[3]))
        elif groups[4] is not None:
            pair = (int(groups[4]), int(groups[5]))
        if pair is None:
            return m.group(0)
        n, k = pair
        try:
            return str(math.comb(n, k))
        except ValueError:
            return m.group(0)

    return _COMB_RE.sub(_sub, s)


def _safe_eval_fraction(expr: str) -> Fraction | None:
    """Evaluate an arithmetic expression over integers (+ - * / and C(n,k))
    as an exact Fraction. Rejects anything non-numeric."""
    s = _replace_combinations(expr)
    # Strip whitespace; reject if any disallowed chars remain
    s = s.strip()
    if not s:
        return None
    if not re.fullmatch(r"[\d\s+\-*/().]+", s):
        return None
    try:
        tree = ast.parse(s, mode="eval")
    except SyntaxError:
        return None

    def _eval(node: ast.AST) -> Fraction:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, int):
                return Fraction(node.value)
            if isinstance(node.value, float):
                return Fraction(node.value).limit_denominator(10**9)
            raise ValueError("unsupported constant")
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            v = _eval(node.operand)
            return v if isinstance(node.op, ast.UAdd) else -v
        if isinstance(node, ast.BinOp):
            left = _eval(node.left)
            right = _eval(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                if right == 0:
                    raise ValueError("div by zero")
                return left / right
            raise ValueError(f"unsupported op {node.op}")
        raise ValueError(f"unsupported node {type(node).__name__}")

    try:
        return _eval(tree)
    except Exception:
        return None


def _to_fraction(s: Any) -> Fraction | None:
    if isinstance(s, (int, float)):
        try:
            return Fraction(s).limit_denominator(10**9)
        except Exception:
            return None
    if not isinstance(s, str):
        return None
    s = s.strip()
    if not s:
        return None
    # Try direct simple parse first (e.g. "90/210", "0.25", "3")
    try:
        if "/" in s and re.fullmatch(r"-?\d+\s*/\s*-?\d+", s):
            num, den = s.split("/", 1)
            return Fraction(int(num.strip()), int(den.strip()))
        if re.fullmatch(r"-?\d+(?:\.\d+)?", s):
            return Fraction(s).limit_denominator(10**9) if "." in s else Fraction(int(s))
    except Exception:
        pass
    # Fallback: safely evaluate arithmetic expressions with C(n,k) / nCk.
    return _safe_eval_fraction(s)


def _extract(
    question_text: str,
    parent_stem: str | None,
    working_steps: list[str],
    client: ModelClient,
) -> dict | None:
    prompt = (
        _EXTRACTOR_PROMPT
        .replace("{parent_stem}", parent_stem or "(none)")
        .replace("{question_text}", question_text or "(empty)")
        .replace("{working_steps}", "\n".join(working_steps) if working_steps else "(none)")
    )
    try:
        raw = client.call(
            ModelRequest(task=TaskType.grade, prompt=prompt, max_tokens=1024, temperature=0.0)
        )
        data = parse_json_object(raw)
        _log.debug("probability extractor output: %s", json.dumps(data, default=str)[:600])
        return data
    except Exception as e:
        _log.warning("probability extractor failed: %s", e)
        return None


_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _parse_student_numeric(s: str | None) -> float | None:
    if not s:
        return None
    s = s.replace("\\approx", "").replace("≈", "").strip()
    # normalise \frac{a}{b}
    s = re.sub(
        r"\\frac\s*\{(-?\d+(?:\.\d+)?)\}\s*\{(-?\d+(?:\.\d+)?)\}",
        lambda m: f"{m.group(1)}/{m.group(2)}",
        s,
    )
    frac_m = None
    for fm in re.finditer(r"(-?\d+(?:\.\d+)?)\s*/\s*(-?\d+(?:\.\d+)?)", s):
        frac_m = fm
    if frac_m:
        try:
            a = float(frac_m.group(1))
            b = float(frac_m.group(2))
            if b != 0:
                return a / b
        except ValueError:
            pass
    matches = list(_NUMBER_RE.finditer(s))
    if matches:
        try:
            return float(matches[-1].group(0))
        except ValueError:
            return None
    return None


def _close(a: float, b: float, rel_tol: float = 0.005, abs_tol: float = 0.001) -> bool:
    import math
    return math.isclose(a, b, rel_tol=rel_tol, abs_tol=abs_tol)


def verify_probability(
    question_text: str,
    student_answer: str | None,
    working_steps: list[str],
    client: ModelClient,
    parent_stem: str | None = None,
) -> ProbVerification:
    data = _extract(question_text, parent_stem, working_steps, client)
    if not data:
        return ProbVerification(verified=False, student_matches=None, detail="extractor failed")

    _log.info("prob-extractor: %s", json.dumps(data, default=str)[:400])

    pattern = (data.get("pattern") or "none").strip()
    target = (data.get("target") or "none").strip()
    if pattern != "distribution" or target == "none":
        return ProbVerification(
            verified=False, student_matches=None, detail=f"pattern={pattern} target={target}"
        )

    dist = data.get("distribution") or []
    probs: dict[float, Fraction] = {}
    for entry in dist:
        x = entry.get("x")
        p = _to_fraction(entry.get("p"))
        if x is None or p is None:
            continue
        try:
            probs[float(x)] = p
        except (TypeError, ValueError):
            continue

    if not probs:
        return ProbVerification(
            verified=False, student_matches=None, detail="distribution empty"
        )

    # Sanity: total probability should sum to 1 (allow tiny rounding).
    total = sum(probs.values(), Fraction(0))
    if total != Fraction(1):
        # tolerate within ±0.001 of 1 since the extractor may drop a zero-prob row
        diff = abs(float(total) - 1.0)
        if diff > 0.002:
            return ProbVerification(
                verified=False,
                student_matches=None,
                detail=f"distribution does not sum to 1 (sum={total})",
            )

    event_a = {float(v) for v in (data.get("event_A") or [])}
    event_b = {float(v) for v in (data.get("event_B") or [])}

    def _p_over(subset: set[float]) -> Fraction:
        return sum((probs[x] for x in probs if x in subset), Fraction(0))

    try:
        if target == "P_A":
            answer = _p_over(event_a)
        elif target == "P_A_and_B":
            answer = _p_over(event_a & event_b)
        elif target == "P_A_given_B":
            num = _p_over(event_a & event_b)
            den = _p_over(event_b)
            if den == 0:
                return ProbVerification(
                    verified=False, student_matches=None, detail="P(B) = 0"
                )
            answer = num / den
        else:
            return ProbVerification(
                verified=False, student_matches=None, detail=f"unknown target {target}"
            )
    except Exception as e:
        return ProbVerification(
            verified=False, student_matches=None, detail=f"compute error: {e}"
        )

    exact = f"{answer.numerator}/{answer.denominator}"
    dec = float(answer)

    student_num = _parse_student_numeric(student_answer)
    if student_num is None:
        match: bool | None = None
    else:
        match = _close(student_num, dec)

    primary = f"\\frac{{{answer.numerator}}}{{{answer.denominator}}} \\approx {dec:.3g}"

    return ProbVerification(
        verified=True,
        student_matches=match,
        primary_answer=primary,
        exact_fraction=exact,
        decimal=dec,
        detail=f"target={target} A={sorted(event_a)} B={sorted(event_b)} answer={exact}≈{dec:.4f}",
    )
