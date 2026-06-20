"""
Classifier：question_text → QuestionType

优先使用关键词规则匹配（零延迟），回退到 LLM 分类。
"""
from __future__ import annotations

import logging
import re

from models.schemas import QuestionType

_log = logging.getLogger("classifier")


_RULES: list[tuple[QuestionType, re.Pattern]] = [
    (
        QuestionType.stationary_points,
        re.compile(
            r"stationary|turning\s+point|maximum\s+point|minimum\s+point"
            r"|nature\s+of|classify.*(point|extrema)"
            r"|find.*(max|min).*point",
            re.IGNORECASE,
        ),
    ),
    (
        QuestionType.integration,
        re.compile(
            r"\bintegrat|∫|area\s+under|definite\s+integral|indefinite\s+integral"
            r"|\bfind\b.*\b∫\b",
            re.IGNORECASE,
        ),
    ),
    (
        QuestionType.differentiation,
        re.compile(
            r"\bdifferentiat|dy/dx|d²y/dx²|d\^2y/dx\^2|\bderivative\b"
            r"|rate\s+of\s+change|\bdy\b.*\bdx\b|gradient\s+of",
            re.IGNORECASE,
        ),
    ),
    (
        QuestionType.trigonometry,
        re.compile(
            r"\b(?:sin|cos|tan|cosec|sec|cot)\b|trigonometr|trig\s+identit"
            r"|radian|degree.*angle|\bangle\b.*(?:sin|cos|tan)"
            r"|sin\^2|cos\^2|double\s+angle|half\s+angle"
            r"|inverse\s+(?:sin|cos|tan)|arc(?:sin|cos|tan)",
            re.IGNORECASE,
        ),
    ),
    (
        QuestionType.logarithms_exponentials,
        re.compile(
            r"\blog\b|\bln\b|logarithm|exponential|e\^|decay\s+model"
            r"|growth\s+model|half[- ]life|\bexp\b",
            re.IGNORECASE,
        ),
    ),
    (
        QuestionType.sequences_series,
        re.compile(
            r"\bsequence\b|\bseries\b|arithmetic\s+progression|geometric\s+progression"
            r"|\bA\.?P\.?\b|\bG\.?P\.?\b|sum\s+to\s+(?:n|infinity)|sigma|Σ|∑"
            r"|binomial\s+expansion|\bnth\s+term\b|common\s+(?:ratio|difference)"
            r"|recurrence|converge|diverge",
            re.IGNORECASE,
        ),
    ),
    (
        QuestionType.coordinate_geometry,
        re.compile(
            r"equation\s+of\s+(?:the\s+)?(?:line|circle|tangent|normal)"
            r"|midpoint|gradient\s+of\s+(?:the\s+)?line|perpendicular\s+bisector"
            r"|distance\s+between.*points|circle.*(?:centre|radius|equation)"
            r"|intersect.*(?:line|curve|circle)|tangent\s+to\s+(?:the\s+)?(?:curve|circle)"
            r"|passing\s+through.*(?:point|coordinate)",
            re.IGNORECASE,
        ),
    ),
    (
        QuestionType.vectors,
        re.compile(
            r"\bvector\b|position\s+vector|magnitude\s+of|direction\s+vector"
            r"|scalar\s+product|dot\s+product|unit\s+vector"
            r"|parallel.*vector|perpendicular.*vector|\b[→⃗]\b",
            re.IGNORECASE,
        ),
    ),
    (
        QuestionType.statistics,
        re.compile(
            r"\bprobabilit|binomial\s+distribut|normal\s+distribut|poisson"
            r"|hypothesis\s+test|significance\s+level|p-value|chi[- ]?squared"
            r"|standard\s+deviation|variance|mean.*(?:data|sample|population)"
            r"|correlation|regression|expected\s+value|\bE\(X\)|\bVar\(",
            re.IGNORECASE,
        ),
    ),
    (
        QuestionType.algebra,
        re.compile(
            r"\bsolve\b.*(?:equation|inequality|simultaneous)|completing\s+the\s+square"
            r"|factoris|quadratic.*(?:equation|formula)|discriminant"
            r"|partial\s+fractions|algebraic\s+(?:fraction|division)"
            r"|remainder\s+theorem|factor\s+theorem|\bproof\b.*\binduction\b"
            r"|simultaneous\s+equation",
            re.IGNORECASE,
        ),
    ),
]


# LLM 分类的 prompt（仅当正则全部未命中时使用）
_CLASSIFY_PROMPT = """\
Classify this A-Level Mathematics question into exactly ONE of these types:
differentiation, integration, stationary_points, algebra, trigonometry, vectors,
sequences_series, coordinate_geometry, logarithms_exponentials, statistics, unknown

Question: {question_text}

Reply with ONLY the type name, nothing else."""


def classify_question(question_text: str, client=None) -> QuestionType:
    """
    关键词分类优先，LLM 回退。
    stationary_points 优先匹配，因为它通常也包含 differentiation 关键词。
    """
    for q_type, pattern in _RULES:
        if pattern.search(question_text):
            return q_type

    # LLM fallback: 当 client 可用且正则全部未命中时
    if client is not None and question_text.strip():
        try:
            from router.models import ModelRequest, TaskType
            request = ModelRequest(
                task=TaskType.classify,
                prompt=_CLASSIFY_PROMPT.format(question_text=question_text),
                max_tokens=50,
                temperature=0.0,
            )
            raw = client.call(request).strip().lower().replace(" ", "_")
            # Validate against known types
            try:
                return QuestionType(raw)
            except ValueError:
                # Try partial match
                for qt in QuestionType:
                    if qt.value in raw:
                        _log.info("LLM classified %r as %s", question_text[:50], qt.value)
                        return qt
        except Exception as e:
            _log.warning("LLM classification failed: %s", e)

    return QuestionType.unknown
