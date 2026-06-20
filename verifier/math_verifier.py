"""
SymPy 数学验证：独立于 LLM 的计算检查。

- 解析 LLM 返回的 correct_answer 和 student_answer 为 SymPy 表达式
- 检查数学等价性 (simplify(a - b) == 0)
- 对微积分题独立计算验证
- 解析失败时静默返回 inconclusive，不阻塞流程
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

_log = logging.getLogger("verifier")


@dataclass
class VerificationResult:
    verified: bool          # True = SymPy 成功完成验证
    sympy_agrees: bool | None  # True/False = SymPy 与 LLM 一致/不一致，None = 无法判断
    sympy_answer: str | None   # SymPy 计算的正确答案（如有）
    detail: str = ""


def _strip_latex(s: str) -> str:
    """Remove LaTeX delimiters and common wrappers."""
    if not s:
        return ""
    s = s.strip()
    # Remove $...$ wrapping
    if s.startswith("$") and s.endswith("$"):
        s = s[1:-1].strip()
    # Remove \displaystyle, \left, \right
    s = re.sub(r"\\(?:displaystyle|left|right)\s*", "", s)
    return s


def _latex_to_sympy_str(latex: str) -> str:
    """Convert common LaTeX math notation to SymPy-parseable string."""
    s = _strip_latex(latex)
    if not s:
        return ""

    # \frac{a}{b} → (a)/(b)
    while r"\frac" in s:
        s = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"(\1)/(\2)", s)

    # \sqrt{x} → sqrt(x), \sqrt[n]{x} → x**(1/n)
    s = re.sub(r"\\sqrt\[(\d+)\]\{([^{}]+)\}", r"(\2)**(1/(\1))", s)
    s = re.sub(r"\\sqrt\{([^{}]+)\}", r"sqrt(\1)", s)

    # \ln → log, \log → log
    s = s.replace(r"\ln", "log")
    s = s.replace(r"\log", "log")

    # Trig functions
    for fn in ("sin", "cos", "tan", "sec", "csc", "cot",
               "arcsin", "arccos", "arctan", "asin", "acos", "atan"):
        s = s.replace(f"\\{fn}", fn)

    # \pi → pi, \e → E
    s = s.replace(r"\pi", "pi")
    s = s.replace(r"\infty", "oo")

    # e^{...} → exp(...)
    s = re.sub(r"e\^\{([^{}]+)\}", r"exp(\1)", s)
    s = re.sub(r"e\^(\w)", r"exp(\1)", s)

    # x^{n} → x**(n)
    s = re.sub(r"\^\{([^{}]+)\}", r"**(\1)", s)
    s = re.sub(r"\^(\w)", r"**\1", s)

    # Remove remaining backslashes (e.g. \cdot → *)
    s = s.replace(r"\cdot", "*")
    s = s.replace(r"\times", "*")
    s = s.replace(r"\div", "/")

    # Remove braces
    s = s.replace("{", "(").replace("}", ")")

    # Implicit multiplication: 2x → 2*x, )x → )*x
    s = re.sub(r"(\d)([a-zA-Z])", r"\1*\2", s)
    s = re.sub(r"\)(\w)", r")*\1", s)

    return s.strip()


def _try_parse(expr_str: str):
    """Try to parse a string as a SymPy expression. Returns None on failure."""
    try:
        from sympy import sympify, Symbol
        from sympy.parsing.sympy_parser import (
            parse_expr,
            standard_transformations,
            implicit_multiplication_application,
            convert_xor,
        )
        transformations = standard_transformations + (
            implicit_multiplication_application,
            convert_xor,
        )
        # Define common symbols
        local_dict = {
            "x": Symbol("x"), "y": Symbol("y"), "t": Symbol("t"),
            "n": Symbol("n"), "C": Symbol("C"),
        }
        return parse_expr(expr_str, local_dict=local_dict, transformations=transformations)
    except Exception:
        return None


def _sympy_equivalence_worker(conn, str_a: str, str_b: str):
    """Multiprocessing worker: check equivalence of two expression strings."""
    try:
        from sympy import simplify, trigsimp, Symbol
        from sympy.parsing.sympy_parser import (
            parse_expr, standard_transformations,
            implicit_multiplication_application, convert_xor,
        )
        transformations = standard_transformations + (
            implicit_multiplication_application, convert_xor,
        )
        local_dict = {
            "x": Symbol("x"), "y": Symbol("y"), "t": Symbol("t"),
            "n": Symbol("n"), "C": Symbol("C"),
        }
        expr_a = parse_expr(str_a, local_dict=local_dict, transformations=transformations)
        expr_b = parse_expr(str_b, local_dict=local_dict, transformations=transformations)
        diff = simplify(expr_a - expr_b)
        equivalent = diff == 0 or simplify(diff).is_zero
        if not equivalent:
            equivalent = trigsimp(diff) == 0
        conn.send(("ok", (str(diff), bool(equivalent), str(expr_a))))
    except Exception as e:
        conn.send(("err", str(e)))
    finally:
        conn.close()


def _run_sympy_with_timeout(worker_func, args, timeout_sec: int = 5):
    """Run a SymPy worker in a subprocess with hard kill timeout."""
    import multiprocessing as _mp
    # Use 'fork' context to avoid 'spawn' deadlocks when called from threads
    ctx = _mp.get_context("fork")
    parent_conn, child_conn = ctx.Pipe()
    proc = ctx.Process(target=worker_func, args=(child_conn, *args), daemon=True)
    proc.start()
    proc.join(timeout=timeout_sec)
    if proc.is_alive():
        proc.kill()
        proc.join(timeout=1)
        _log.warning("SymPy computation killed after %ds timeout", timeout_sec)
        parent_conn.close()
        return None
    if parent_conn.poll():
        tag, val = parent_conn.recv()
        parent_conn.close()
        if tag == "ok":
            return val
        _log.debug("SymPy computation error: %s", val)
        return None
    parent_conn.close()
    return None


_MULTI_VALUE_SPLIT = re.compile(
    r"\s*(?:,|;|\bor\b|\\text\{or\}|或)\s*",
    re.IGNORECASE,
)


def _expand_plus_minus(s: str) -> list[str]:
    """Expand `a ± b` / `a \\pm b` into [`a + b`, `a - b`]. If no ±, return [s]."""
    if not s:
        return [s]
    # Normalise both \pm and unicode ±
    marker = "\x00PM\x00"
    norm = s.replace(r"\pm", marker).replace("±", marker)
    if marker not in norm:
        return [s]
    plus_form = norm.replace(marker, "+")
    minus_form = norm.replace(marker, "-")
    return [plus_form, minus_form]


def _split_and_expand(raw: str) -> list[str]:
    """Split an answer string into one or more sympy-parseable sub-expressions.

    Handles:
      - comma / ';' / 'or' / 中文 '或' separated multi-value answers
      - `±` / `\\pm` branches (each branch duplicated into + and -)
      - leading `x =` / `y =` assignments are stripped
    """
    if not raw:
        return []
    cleaned = _strip_latex(raw)
    # Strip leading `var =` assignments so we just compare values
    cleaned = re.sub(r"^\s*[a-zA-Z]\s*=\s*", "", cleaned)
    parts = [p.strip() for p in _MULTI_VALUE_SPLIT.split(cleaned) if p.strip()]
    if not parts:
        parts = [cleaned]
    expanded: list[str] = []
    for p in parts:
        for branch in _expand_plus_minus(p):
            s = _latex_to_sympy_str(branch)
            if s:
                expanded.append(s)
    return expanded


def verify_equivalence(answer_a: str, answer_b: str) -> VerificationResult:
    """
    Check if two mathematical expressions are equivalent.

    Supports multi-value answers (quadratic roots, etc.) separated by
    `,`, `or`, `or` 或 `±`. Two answers are equivalent iff they describe the
    SAME SET of values (each side's values match the other's).

    Uses a subprocess with hard timeout to prevent SymPy hangs.
    """
    values_a = _split_and_expand(answer_a)
    values_b = _split_and_expand(answer_b)

    if not values_a or not values_b:
        return VerificationResult(verified=False, sympy_agrees=None, sympy_answer=None,
                                  detail="could not extract expression text")

    # Fast path: exactly one value on each side → direct compare
    if len(values_a) == 1 and len(values_b) == 1:
        result = _run_sympy_with_timeout(
            _sympy_equivalence_worker, (values_a[0], values_b[0]), timeout_sec=5,
        )
        if result is None:
            return VerificationResult(verified=False, sympy_agrees=None, sympy_answer=None,
                                      detail="simplify timed out or failed")
        diff_str, equivalent, expr_a_str = result
        return VerificationResult(
            verified=True,
            sympy_agrees=bool(equivalent),
            sympy_answer=expr_a_str,
            detail=f"simplify diff = {diff_str}",
        )

    # Multi-value: require set equality (every a has a match in b, and vice versa)
    def _any_match(target: str, pool: list[str]) -> bool | None:
        for cand in pool:
            r = _run_sympy_with_timeout(
                _sympy_equivalence_worker, (target, cand), timeout_sec=3,
            )
            if r is None:
                continue
            _diff, equiv, _expr = r
            if equiv:
                return True
        return False

    a_all_in_b = all(_any_match(a, values_b) for a in values_a)
    b_all_in_a = all(_any_match(b, values_a) for b in values_b)
    equivalent = bool(a_all_in_b and b_all_in_a)
    return VerificationResult(
        verified=True,
        sympy_agrees=equivalent,
        sympy_answer=values_a[0],
        detail=(
            f"multi-value compare: A={values_a} B={values_b} "
            f"(a⊆b={a_all_in_b}, b⊆a={b_all_in_a})"
        ),
    )


def verify_derivative(expression: str, variable: str = "x") -> VerificationResult:
    """Independently compute derivative and return result."""
    try:
        from sympy import diff, Symbol, simplify
    except ImportError:
        return VerificationResult(verified=False, sympy_agrees=None, sympy_answer=None)

    expr_str = _latex_to_sympy_str(expression)
    expr = _try_parse(expr_str)
    if expr is None:
        return VerificationResult(verified=False, sympy_agrees=None, sympy_answer=None,
                                  detail=f"parse failed: {expr_str!r}")

    try:
        var = Symbol(variable)
        result = simplify(diff(expr, var))
        return VerificationResult(
            verified=True, sympy_agrees=None,
            sympy_answer=str(result),
            detail=f"d/d{variable}({expr}) = {result}",
        )
    except Exception as e:
        return VerificationResult(verified=False, sympy_agrees=None, sympy_answer=None,
                                  detail=f"diff error: {e}")


def verify_integral(expression: str, variable: str = "x") -> VerificationResult:
    """Independently compute indefinite integral and return result."""
    try:
        from sympy import integrate, Symbol, simplify
    except ImportError:
        return VerificationResult(verified=False, sympy_agrees=None, sympy_answer=None)

    expr_str = _latex_to_sympy_str(expression)
    expr = _try_parse(expr_str)
    if expr is None:
        return VerificationResult(verified=False, sympy_agrees=None, sympy_answer=None,
                                  detail=f"parse failed: {expr_str!r}")

    try:
        var = Symbol(variable)
        result = simplify(integrate(expr, var))
        return VerificationResult(
            verified=True, sympy_agrees=None,
            sympy_answer=str(result),
            detail=f"∫({expr})d{variable} = {result}",
        )
    except Exception as e:
        return VerificationResult(verified=False, sympy_agrees=None, sympy_answer=None,
                                  detail=f"integrate error: {e}")


def _extract_expression_from_question(question_text: str, question_type: str) -> str | None:
    """
    Try to extract the mathematical expression to differentiate/integrate from the question text.
    Returns a LaTeX string or None if extraction fails.
    """
    if not question_text:
        return None

    text = question_text.strip()

    # Pattern: "Differentiate y = ..." or "Find dy/dx of ..."
    if question_type == "differentiation":
        patterns = [
            r'[Dd]ifferentiate\s+(?:y\s*=\s*)?(.+?)(?:\.|$)',
            r'[Ff]ind\s+(?:dy/dx|d/dx|the derivative)\s+(?:of|for|when)\s+(?:y\s*=\s*)?(.+?)(?:\.|$)',
            r'y\s*=\s*(.+?)(?:\.\s|,\s|\s+[Ff]ind|\s+[Dd]etermine|$)',
            r'f\s*\(\s*x\s*\)\s*=\s*(.+?)(?:\.\s|,\s|\s+[Ff]ind|$)',
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                return m.group(1).strip().rstrip('.')
        return None

    # Pattern: "Integrate ..." or "Find the integral of ..."
    if question_type == "integration":
        patterns = [
            r'[Ii]ntegrate\s+(.+?)(?:\s+with respect|\s+w\.?r\.?t|\.|$)',
            r'[Ff]ind\s+(?:the\s+)?(?:indefinite\s+)?integral\s+(?:of\s+)?(.+?)(?:\s+with respect|\.|$)',
            r'∫\s*(.+?)\s*d[xtyu]',
            r'\\int\s*(.+?)\s*d[xtyu]',
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                return m.group(1).strip().rstrip('.')
        return None

    return None


def _sympy_solve_worker(conn, expr_str_inner: str, q_type: str):
    """Multiprocessing worker: independently solve diff/integration."""
    try:
        from sympy import diff as _diff, integrate as _integrate, Symbol, simplify as _simp
        from sympy.parsing.sympy_parser import (
            parse_expr, standard_transformations,
            implicit_multiplication_application, convert_xor,
        )
        transformations = standard_transformations + (
            implicit_multiplication_application, convert_xor,
        )
        local_dict = {
            "x": Symbol("x"), "y": Symbol("y"), "t": Symbol("t"),
            "n": Symbol("n"), "C": Symbol("C"),
        }
        e = parse_expr(expr_str_inner, local_dict=local_dict, transformations=transformations)
        x = Symbol("x")
        if q_type == "differentiation":
            r = _simp(_diff(e, x))
        elif q_type == "integration":
            r = _simp(_integrate(e, x))
        else:
            conn.send(("err", "unsupported")); conn.close(); return
        conn.send(("ok", str(r)))
    except Exception as ex:
        conn.send(("err", str(ex)))
    finally:
        conn.close()


def _independently_solve(expression_latex: str, question_type: str) -> VerificationResult:
    """
    Use SymPy to independently compute the correct answer for differentiation/integration.
    """
    expr_str = _latex_to_sympy_str(expression_latex)
    if not expr_str:
        return VerificationResult(verified=False, sympy_agrees=None, sympy_answer=None,
                                  detail=f"could not convert to sympy: {expression_latex!r}")

    result = _run_sympy_with_timeout(_sympy_solve_worker, (expr_str, question_type), timeout_sec=10)
    if result is None:
        return VerificationResult(verified=False, sympy_agrees=None, sympy_answer=None,
                                  detail="SymPy computation timed out")

    return VerificationResult(
        verified=True,
        sympy_agrees=None,
        sympy_answer=result,
        detail=f"SymPy computed: {result}",
    )


def verify_grade(
    question_text: str,
    student_answer: str,
    correct_answer: str | None,
    question_type: str,
    is_correct: bool,
) -> VerificationResult:
    """
    Top-level verification entry point.

    1. For differentiation/integration: try to independently solve and validate correct_answer
    2. Check equivalence between student answer and correct answer
    3. Report whether SymPy agrees with the LLM's grading
    """
    if not correct_answer or not student_answer:
        return VerificationResult(verified=False, sympy_agrees=None, sympy_answer=None,
                                  detail="missing answer(s)")

    # --- Phase 1: Independent solve for diff/integration ---
    sympy_independent_answer: str | None = None
    if question_type in ("differentiation", "integration"):
        extracted = _extract_expression_from_question(question_text, question_type)
        if extracted:
            solve_result = _independently_solve(extracted, question_type)
            if solve_result.verified and solve_result.sympy_answer:
                sympy_independent_answer = solve_result.sympy_answer
                _log.info(
                    "SymPy independent solve: %s → %s",
                    extracted, sympy_independent_answer,
                )

                # Compare SymPy's answer with LLM's correct_answer
                llm_str = _latex_to_sympy_str(correct_answer)
                llm_expr = _try_parse(llm_str) if llm_str else None
                sympy_expr = _try_parse(sympy_independent_answer)

                if llm_expr is not None and sympy_expr is not None:
                    try:
                        from sympy import simplify
                        cmp_result = _run_sympy_with_timeout(
                            _sympy_equivalence_worker,
                            (llm_str, sympy_independent_answer),
                            timeout_sec=5,
                        )
                        if cmp_result is None:
                            _log.warning("SymPy comparison timed out")
                            return VerificationResult(verified=False, sympy_agrees=None,
                                                      sympy_answer=sympy_independent_answer,
                                                      detail="SymPy comparison timed out")
                        diff_val, llm_matches_sympy, _ = cmp_result
                        if not llm_matches_sympy:
                            _log.warning(
                                "LLM correct_answer DISAGREES with SymPy! "
                                "LLM=%s, SymPy=%s, diff=%s",
                                correct_answer, sympy_independent_answer, diff_val,
                            )
                            # Return with sympy_answer so caller can override
                            return VerificationResult(
                                verified=True,
                                sympy_agrees=False,
                                sympy_answer=sympy_independent_answer,
                                detail=f"LLM correct_answer={correct_answer} DISAGREES with "
                                       f"SymPy={sympy_independent_answer} (diff={diff_val})",
                            )
                        else:
                            _log.info("LLM correct_answer confirmed by SymPy")
                    except Exception as e:
                        _log.debug("Could not compare LLM vs SymPy: %s", e)

    # --- Phase 2: Check student vs correct equivalence ---
    result = verify_equivalence(correct_answer, student_answer)
    if result.verified and result.sympy_agrees is not None:
        agrees_with_llm = (result.sympy_agrees == is_correct)
        return VerificationResult(
            verified=True,
            sympy_agrees=agrees_with_llm,
            sympy_answer=sympy_independent_answer or result.sympy_answer,
            detail=result.detail + f" | LLM says is_correct={is_correct}, "
                   f"SymPy says equivalent={result.sympy_agrees}",
        )

    # If we got an independent answer but couldn't verify equivalence, still return it
    if sympy_independent_answer:
        return VerificationResult(
            verified=True,
            sympy_agrees=None,
            sympy_answer=sympy_independent_answer,
            detail=f"SymPy computed answer={sympy_independent_answer}, "
                   f"but could not verify student equivalence",
        )

    return result
