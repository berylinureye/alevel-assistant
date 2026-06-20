"""
解题思路计算验证：后处理方案

模型生成完后，用 SymPy 扫描验证所有计算步骤，发现算错就修正。
耗时 < 1 秒，不依赖 Function Calling。

两层防御：
  - Prompt 层：强制以正确答案为锚点反向推导（防公式错/数据错）
  - 后处理层：SymPy 扫描验证（防算术错，如 186+910 写成 1086）
"""
from __future__ import annotations

import logging
import re

_log = logging.getLogger("solution_verifier")

try:
    from sympy import sympify, N
    _HAS_SYMPY = True
except ImportError:
    _HAS_SYMPY = False
    _log.warning("SymPy not installed, solution verification disabled")


# ---------------------------------------------------------------------------
# 1.1 从解题思路文本中提取计算表达式
# ---------------------------------------------------------------------------

def extract_calculations(text: str) -> list[dict]:
    """
    从解题思路文本中提取所有 "表达式 = 数值" 的计算步骤。

    示例匹配：
      "$12 \\times 15.5 = 186$"
      "$(186 + 910) \\div 32 = 34.25$"
      "\\frac{186 + 910}{32} = 34.25"
      "3. = 137/4"
    """
    calculations: list[dict] = []
    seen_spans: set[tuple[int, int]] = set()

    patterns = [
        # LaTeX \frac{a}{b} = c
        (r'\\frac\{([^}]+)\}\{([^}]+)\}\s*=\s*([\d.]+(?:/[\d.]+)?)', "frac"),
        # (a + b) / c = d  or  (a + b) ÷ c = d
        (r'(\([^)]+\)\s*[/÷]\s*[\d.]+)\s*=\s*([\d.]+)', "expr"),
        # a × b + c = d (chained arithmetic)
        (r'([\d.]+\s*[×✕\*]\s*[\d.]+(?:\s*[+\-×✕\*/÷]\s*[\d.]+)*)\s*=\s*([\d.]+(?:/[\d.]+)?)', "expr"),
        # a / b = c
        (r'([\d.]+\s*/\s*[\d.]+)\s*=\s*([\d.]+)', "expr"),
        # a + b = c
        (r'([\d.]+\s*\+\s*[\d.]+)\s*=\s*([\d.]+)', "expr"),
        # a - b = c
        (r'([\d.]+\s*\-\s*[\d.]+)\s*=\s*([\d.]+)', "expr"),
    ]

    for pattern, kind in patterns:
        for match in re.finditer(pattern, text):
            span = (match.start(), match.end())
            # 避免重叠匹配
            if any(s[0] <= span[0] < s[1] or s[0] < span[1] <= s[1] for s in seen_spans):
                continue

            groups = match.groups()
            if kind == "frac" and len(groups) == 3:
                expr = f"({groups[0]}) / ({groups[1]})"
                claimed = groups[2]
            elif len(groups) == 2:
                expr = groups[0]
                claimed = groups[1]
            else:
                continue

            # LaTeX 符号 → Python 运算符
            expr_clean = (
                expr
                .replace('×', '*').replace('✕', '*')
                .replace('÷', '/').replace('\\div', '/')
                .replace('\\times', '*').replace('\\cdot', '*')
                .strip()
            )

            calculations.append({
                "original": match.group(0),
                "expression": expr_clean,
                "claimed_result": claimed.strip(),
                "start": match.start(),
                "end": match.end(),
            })
            seen_spans.add(span)

    return calculations


# ---------------------------------------------------------------------------
# 1.2 用 SymPy 验证每一步
# ---------------------------------------------------------------------------

def verify_calculation(expression: str, claimed_result: str) -> dict:
    """
    验证单个计算步骤是否正确。
    返回: {"is_correct": bool, "actual_result": str}
    """
    if not _HAS_SYMPY:
        return {"is_correct": True, "actual_result": claimed_result}

    try:
        actual = sympify(expression)
        claimed = sympify(claimed_result)

        # 允许浮点误差 1e-6
        diff = abs(float(N(actual - claimed)))
        is_correct = diff < 1e-6

        # 格式化实际结果
        if actual.is_Integer:
            actual_str = str(int(actual))
        elif actual.is_Rational:
            decimal = float(actual)
            if decimal == int(decimal):
                actual_str = str(int(decimal))
            else:
                actual_str = str(round(decimal, 6))
        else:
            actual_str = str(round(float(N(actual)), 6))

        return {"is_correct": is_correct, "actual_result": actual_str}

    except Exception:
        # 无法解析 → 跳过不动
        return {"is_correct": True, "actual_result": claimed_result}


# ---------------------------------------------------------------------------
# 1.3 扫描全文，修正错误
# ---------------------------------------------------------------------------

def verify_and_fix_solution(text: str) -> tuple[str, list[dict]]:
    """
    扫描解题思路中的所有计算，验证并修正。

    Returns:
        (修正后的文本, 修正记录列表)
    """
    if not _HAS_SYMPY:
        return text, []

    calculations = extract_calculations(text)
    fixes: list[dict] = []
    fixed_text = text

    # 从后往前替换，避免位置偏移
    for calc in reversed(calculations):
        result = verify_calculation(calc["expression"], calc["claimed_result"])

        fix_record = {
            "expression": calc["expression"],
            "claimed": calc["claimed_result"],
            "actual": result["actual_result"],
            "fixed": not result["is_correct"],
        }
        fixes.append(fix_record)

        if not result["is_correct"]:
            old_text = calc["original"]
            new_text = old_text.replace(calc["claimed_result"], result["actual_result"])
            fixed_text = fixed_text[:calc["start"]] + new_text + fixed_text[calc["end"]:]
            _log.info(
                "Solution fix: %s = %s (was %s)",
                calc["expression"], result["actual_result"], calc["claimed_result"],
            )

    fixes.reverse()
    return fixed_text, fixes


# ---------------------------------------------------------------------------
# 清理自我纠结内容
# ---------------------------------------------------------------------------

_HESITATION_PATTERNS = [
    # "wait, no: ..." / "wait — no: ..." 整句删
    r'(?:—\s*)?[Ww]ait,?\s*no[:：,，][^.。\n]*[.。\n]?',
    # "— wait, recompute carefully: ..." / "wait, let me recompute" 整句删
    r'(?:—\s*)?[Ww]ait,?\s+(?:recompute|recalculate|recheck|let\s+(?:me|us)\s+re\w+)[^.。\n]*[.。\n]?',
    # "X is wrong. Let's solve properly." / "... is incorrect. Let me redo..."
    r'(?:\$?[^$\n]*\$?\s*)?is\s+(?:wrong|incorrect)\.\s*[Ll]et(?:\'?s?|\s+(?:me|us))\s+(?:solve|redo|retry|try)[^.。\n]*[.。\n]?',
    # "But that contradicts..." 整句删
    r'[Bb]ut that contradicts[^.。\n]*[.。\n]?',
    # "Let me recalculate" / "Let's recompute" / "Let us recheck" / "Let's solve properly" 整句删
    r"[Ll]et(?:'?s?|\s+(?:me|us))\s+(?:re(?:calculate|compute|check|verify|do|try)|solve\s+properly|try\s+again)[^.。\n]*[.。\n]?",
    # "Actually, that's/it's/this is wrong..." 自我纠正（收紧匹配，避免误删正常 actually）
    r"[Aa]ctually,?\s+(?:that(?:'?s|\s+is)|it(?:'?s|\s+is)|this\s+is)\s+(?:wrong|incorrect|not\s+right)[^.。\n]*[.。\n]?",
    # "Hmm, ..." 开头的犹豫
    r'[Hh]mm,?\s+[^.。\n]*[.。\n]?',
    # "need to verify original problem context" 类元评论
    r'[Nn]eed to verify[^.。\n]*[.。\n]?',
]

_FORBIDDEN_META_PATTERNS = [
    r'^\s*【?\s*学生(?:的)?作答\s*】?\s*[:：]?',
    r'^\s*【?\s*学生答案\s*】?\s*[:：]?',
    r'^\s*【?\s*学生步骤\s*】?\s*[:：]?',
    r'^\s*【?\s*正确答案\s*】?\s*[:：]?',
    r'^\s*【?\s*批改反馈\s*】?\s*[:：]?',
    r'^\s*【?\s*要求\s*】?\s*[:：]?',
    r'^\s*【?\s*内部参考\s*】?\s*[:：]?',
    r'重要\s*[:：]\s*正确答案',
    r'先确认解题路径',
    r'如果你计算出的结果和正确答案不一致',
    r'绝对不要输出',
    r'你的解题过程必须',
]

_STEP_LINE_PATTERN = r'^\s*第\s*\d+\s*步\s*[:：]'


def clean_solution_output(text: str) -> str:
    """
    删除模型输出中的犹豫/自我纠正内容，并做 LaTeX 分隔符规整。
    """
    cleaned = text
    for pattern in _HESITATION_PATTERNS:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

    # LaTeX 分隔符统一：\( \) → $ $；\[ \] → $$ $$（部分模型喜欢 TeX 原生分隔符）
    cleaned = re.sub(r'\\\[([\s\S]+?)\\\]', lambda m: f'$${m.group(1)}$$', cleaned)
    cleaned = re.sub(r'\\\(([\s\S]+?)\\\)', lambda m: f'${m.group(1)}$', cleaned)

    # 裸 LaTeX 保护：检测到连续的 LaTeX token 在 $ 外时，自动包一层 $...$
    cleaned = _wrap_bare_latex_runs(cleaned)

    # 纯正则 LaTeX 规整：合并割裂的 $..$、吸入漏网下标/上标 token
    cleaned = polish_latex(cleaned)

    # 纯整数 \frac{a}{b} 约到最简（24/210 → 4/35）
    from utils.latex_simplify import simplify_latex_fractions
    cleaned = simplify_latex_fractions(cleaned)

    # 清理多余空行
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()


# 常见数学命令 / 符号片段——出现这些且不在 $ 内时，视为泄漏的裸 LaTeX
_BARE_LATEX_RUN = re.compile(
    r"(?:\\(?:frac|sqrt|sum|prod|int|lim|left|right|cdot|times|div|pm|mp|"
    r"triangle|circ|angle|perp|parallel|cong|sim|degree|"
    r"alpha|beta|gamma|delta|epsilon|theta|lambda|mu|sigma|phi|psi|omega|pi|infty|"
    r"mathbf|mathbb|mathcal|boldsymbol|vec|hat|bar|tilde|overline|underline|"
    r"sin|cos|tan|log|ln|exp|ldots|cdots|dots|to|leq|geq|neq|approx|equiv|"
    r"partial|nabla|in|notin|subset|supset|cup|cap|forall|exists)"
    r"(?:\{[^{}]*\}|\^[^ ]{0,10}|_[^ ]{0,10})*"
    r"(?:\s*\\[a-zA-Z]+(?:\{[^{}]*\}|\^[^ ]{0,10}|_[^ ]{0,10})*)*)"
)


# ---------------------------------------------------------------------------
# LaTeX 后处理：合并割裂的 $..$、兜底包裹漏网数学 token（纯正则，无 AI）
# ---------------------------------------------------------------------------

# 两个 $..$ 之间只隔着运算符 / LaTeX 关系符 → 合并成一个
_MERGE_OP = re.compile(
    r'\$([^$\n]+?)\$'
    r'(\s*(?:[+\-*/=<>]+|\\(?:cdot|times|div|pm|mp|leq|geq|neq|approx|to|ge|le|ne))\s*)'
    r'\$([^$\n]+?)\$'
)

# $..$ 后紧跟一个带下标/上标/LaTeX 命令的 token → 吸入 $..$
_ABSORB_TRAIL = re.compile(
    r'\$([^$\n]+?)\$(\s+)('
    r'[A-Za-z](?:_\{[^{}]+\}|_[A-Za-z0-9]|\^\{[^{}]+\}|\^-?[A-Za-z0-9])+'
    r'|\d+(?:\.\d+)?(?:\^\{[^{}]+\}|\^-?\d+)'
    r'|\\[A-Za-z]+(?:\{[^{}]*\})*'
    r')(?![\w])'
)

# $..$ 前紧跟一个数学 token → 吸入 $..$（对称处理）
_ABSORB_LEAD = re.compile(
    r'(?<![\w$\\])('
    r'[A-Za-z](?:_\{[^{}]+\}|_[A-Za-z0-9]|\^\{[^{}]+\}|\^-?[A-Za-z0-9])+'
    r'|\\[A-Za-z]+(?:\{[^{}]*\})*'
    r')(\s+)\$([^$\n]+?)\$'
)

# $..$ = 数字/变量 → 合并（吸入等号右边）
_ABSORB_EQ_RHS = re.compile(
    r'\$([^$\n]+?)\$(\s*=\s*)(-?\d+(?:\.\d+)?|\\?[A-Za-z]\w*)(?![\w{])'
)

# 漏在 $ 外的带下标/上标 token
_BARE_SUBSUP = re.compile(
    r'(?<![\\$\w])('
    r'[A-Za-z](?:_\{[^{}]+\}|_[A-Za-z0-9]|\^\{[^{}]+\}|\^-?[A-Za-z0-9])+'
    r')(?![\w$])'
)


def _iter_merge(pattern: re.Pattern, repl, text: str, limit: int = 8) -> str:
    """应用到收敛为止，防死循环最多 limit 轮。"""
    for _ in range(limit):
        new_text = pattern.sub(repl, text)
        if new_text == text:
            return text
        text = new_text
    return text


def _fix_malformed_dollars(text: str) -> str:
    """
    清除 LLM 插错位置的 `$`：
      - `\\cmd$` 在命令与参数之间：`\\frac${...}` → `\\frac{...}`
      - `$` 出现在 `{...}` 内部：`\\lambda^{x_i$}` → `\\lambda^{x_i}`
    这两种都会让 KaTeX 把整段当纯文本渲染。
    """
    if '$' not in text or '\\' not in text:
        return text

    # 1) 命令与参数之间的 $：\frac$ / \left$ / \right$ / \sum$ ...
    #    紧跟 `{` 或 `(` 时一定是错位
    text = re.sub(r'(\\[A-Za-z]+)\$(?=[\{\(\[])', r'\1', text)
    #    或紧跟空白后再接 `{` 也算错位（偶现）
    text = re.sub(r'(\\[A-Za-z]+)\$(\s*)(?=[\{\(\[])', r'\1\2', text)
    # 反斜杠接单字符的空格命令：\!$ → \!
    text = re.sub(r'(\\[!,;:>])\$', r'\1', text)

    # 2) 大括号深度 > 0 时遇到的 $ 全部丢掉
    out = []
    depth = 0
    for ch in text:
        if ch == '{':
            depth += 1
            out.append(ch)
        elif ch == '}':
            depth = max(0, depth - 1)
            out.append(ch)
        elif ch == '$' and depth > 0:
            continue  # drop
        else:
            out.append(ch)
    text = ''.join(out)

    # 3) 清理连续的 `$$`（把挨在一起的空 span 合并掉）
    text = re.sub(r'\$\$+', '$$', text)
    # `$ $` 空 span
    text = re.sub(r'\$\s+\$', ' ', text)
    return text


_LATEX_CMD_RE = re.compile(r'\\[A-Za-z]+')
_CHINESE_RE = re.compile(r'[\u4e00-\u9fff]')
# 英文散文词：长度 ≥ 3 的纯字母 token，且前面不是反斜杠（即不是 \theta / \alpha）
_PROSE_WORD_RE = re.compile(r'(?<!\\)\b[A-Za-z]{3,}\b')
# 点分缩写：i.i.d. / e.g. / i.e. / etc.
_PROSE_ABBREV_RE = re.compile(r'\b[a-zA-Z](?:\.[a-zA-Z]){1,}\.?')
# 典型数学英文名词白名单：出现不算散文（Poisson/Beta/Gamma 之类分布名、sin/cos/log、iid 之类）
_MATHY_PROSE = frozenset({
    'sin', 'cos', 'tan', 'sec', 'csc', 'cot', 'log', 'ln', 'exp', 'lim', 'max', 'min',
    'sup', 'inf', 'det', 'tr', 'arg', 'var', 'cov', 'mod', 'gcd', 'lcm',
    'iid', 'pdf', 'cdf', 'pmf', 'mle', 'mse', 'iff',
    'poisson', 'normal', 'beta', 'gamma', 'binom', 'binomial', 'bernoulli',
    'uniform', 'exponential', 'chi', 'student',
})


def _is_math_heavy_line(stripped: str) -> bool:
    """判断一行是否是"可以整行剥光 $ 重包"的纯数学行。
    核心：LaTeX 命令多、`$` 多、中文少、**非数学的英文散文词也要少**。
    """
    if not stripped or '$' not in stripped:
        return False
    if len(_LATEX_CMD_RE.findall(stripped)) < 2:
        return False
    if stripped.count('$') < 2:
        return False
    if len(_CHINESE_RE.findall(stripped)) >= 3:
        return False  # 有中文散文
    # 英文散文词（去掉数学专用词白名单）
    prose_words = [w for w in _PROSE_WORD_RE.findall(stripped) if w.lower() not in _MATHY_PROSE]
    if len(prose_words) >= 2:
        return False  # 有英文散文（where / when / find / known / let / etc.）
    if _PROSE_ABBREV_RE.search(stripped):
        return False  # i.i.d. / e.g. / i.e. / etc. 也是散文迹象
    return True


def _rewrap_math_heavy_lines(text: str) -> str:
    """
    对被判定为纯数学行的行：剥光 `$`，整行重包一个 `$...$`。
    收紧判据避免误伤带英文/中文解释的混合行（例如 "Let $X$ be ... where $\\theta > 0$"）。
    """
    lines = text.split('\n')
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not _is_math_heavy_line(stripped):
            continue

        # 剥光 $ 后整行重包
        bare = stripped.replace('$', '')
        # 保留尾部标点（. 。 , ， ; ； : ：）在 $ 外
        m = re.match(r'^(.*?)([.。，,;；:：]*)$', bare)
        if m:
            body, tail = m.group(1), m.group(2)
        else:
            body, tail = bare, ''
        # 保留原缩进
        indent_match = re.match(r'^(\s*)', line)
        indent = indent_match.group(1) if indent_match else ''
        lines[i] = f'{indent}${body}${tail}'
    return '\n'.join(lines)


def _balance_odd_dollars(text: str) -> str:
    """
    行内 `$` 是奇数个时，在行尾（末尾标点前）补一个 `$`。
    兜底，防止单条畸形行污染整页渲染。
    """
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if line.count('$') % 2 != 1:
            continue
        m = re.match(r'^(.*?)([.。，,;；:：\s]*)$', line)
        if m:
            body, tail = m.group(1), m.group(2)
            lines[i] = f'{body}${tail}'
        else:
            lines[i] = line + '$'
    return '\n'.join(lines)


def polish_latex(text: str) -> str:
    """
    对已经有 `$..$` 标记的文本做一次纯正则 LaTeX 规整，不调用任何 AI。

    修复：
      0) `\\frac${...}`、`\\lambda^{x_i$}` 畸形嵌套 $  →  先清理
      1) `$a$ + $b$` → `$a + b$`              （运算符割裂）
      2) `$\\sum$ Y_i` → `$\\sum Y_i$`        （下标/命令漏网）
      3) `x_i` 裸在 $ 外  → `$x_i$`           （完全没包）
    """
    if not text:
        return text

    # Pass 0：先处理畸形 $（必须在合并/吸入之前，否则错位 $ 会打乱 pairing）
    text = _fix_malformed_dollars(text)

    # Pass 0.5：纯数学行整行重包（处理 $ 位置错乱到无法局部修的情况）
    text = _rewrap_math_heavy_lines(text)

    # Pass 1：合并相邻 $..$ 串接
    text = _iter_merge(_MERGE_OP, lambda m: f'${m.group(1)}{m.group(2)}{m.group(3)}$', text)
    # Pass 2：吸入尾部 token
    text = _iter_merge(_ABSORB_TRAIL, lambda m: f'${m.group(1)}{m.group(2)}{m.group(3)}$', text)
    # Pass 3：吸入头部 token
    text = _iter_merge(_ABSORB_LEAD, lambda m: f'${m.group(1)}{m.group(2)}{m.group(3)}$', text)
    # Pass 4：吸入等号右边 RHS
    text = _iter_merge(_ABSORB_EQ_RHS, lambda m: f'${m.group(1)}{m.group(2)}{m.group(3)}$', text)

    # Pass 5：把 $ 外的裸下标/上标 token 包起来（分段处理，不碰 $ 内）
    if '$' in text:
        parts = text.split('$')
        for i in range(0, len(parts), 2):
            parts[i] = _BARE_SUBSUP.sub(lambda m: f'${m.group(1)}$', parts[i])
        text = '$'.join(parts)
    else:
        text = _BARE_SUBSUP.sub(lambda m: f'${m.group(1)}$', text)

    # Pass 6：新包出的 token 可能又构成 $a$ + $b$，再合并一轮
    text = _iter_merge(_MERGE_OP, lambda m: f'${m.group(1)}{m.group(2)}{m.group(3)}$', text)

    # 清理：`$$` 空对 / `$ $` 空对
    text = re.sub(r'\$\s*\$', '', text)

    # 最后兜底：行内 $ 奇数个 → 行尾补一个
    text = _balance_odd_dollars(text)
    return text


def _wrap_bare_latex_runs(text: str) -> str:
    """
    把不在 `$...$` 里的裸 LaTeX 片段自动用 `$...$` 包起来。
    避免 LLM 偶尔漏加 $ 导致前端把 \\sum、\\frac 当作纯文本 escape 显示。
    思路：按 `$` 分段，只处理奇偶段中偶数段（即 $ 之外），找到裸 LaTeX 后包一层 $。
    """
    if '\\' not in text:
        return text
    parts = text.split('$')
    # parts[0], parts[2], ... 是 $ 之外；parts[1], parts[3], ... 是 $ 之内
    for i in range(0, len(parts), 2):
        seg = parts[i]
        if '\\' not in seg:
            continue
        # 对每个裸 LaTeX run 包 $...$
        parts[i] = _BARE_LATEX_RUN.sub(lambda m: f'${m.group(0)}$', seg)
    return '$'.join(parts)


def has_forbidden_solution_style(text: str) -> bool:
    """
    检测是否出现了“批改稿/提示词回显/点评稿”式的解题输出。
    这类内容不应直接展示给学生。
    """
    if not text:
        return False
    return any(
        re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        for pattern in _FORBIDDEN_META_PATTERNS
    )


_NUMBERED_ITEM_PATTERN = r'^\s*\d+\s*[\.、)]\s*.+'
_CONCLUSION_PATTERN = r'(?:∴|\\therefore|因此|所以|答案为)'


def has_expected_solution_structure(
    text: str,
    *,
    require_mistake_section: bool = False,
    require_self_check: bool = False,
    allow_proof_conclusion: bool = True,
) -> bool:
    """
    检测解题思路是否符合面向学生展示的简洁编号列表结构。

    新模板（PROMPT_E_NUMBERED）要求：
      1. 式子 —— 解释
      2. 式子 —— 解释
      ...
      ∴ 答案

    兼容旧模板（PROMPT_B 的"关键思路 + 第 N 步 + 因此，答案为"），以防切换过渡期。
    require_mistake_section / require_self_check 已弃用（新模板不需要），保留参数签名向后兼容。
    """
    _ = (require_mistake_section, require_self_check)  # noqa: F841 — kept for backward compat
    if not text:
        return False

    # 新格式：至少 2 个编号条目 + 一个收束（∴ / 因此 / 所以 / 答案为 / 得证）
    numbered_count = len(re.findall(_NUMBERED_ITEM_PATTERN, text, flags=re.MULTILINE))
    has_conclusion = bool(re.search(_CONCLUSION_PATTERN, text))
    if numbered_count >= 2 and has_conclusion:
        return True

    # 旧格式后备：关键思路 + 第 N 步 + 因此答案为/得证
    if re.search(r'^\s*关键思路\s*[:：]', text, flags=re.MULTILINE) and re.search(
        _STEP_LINE_PATTERN, text, flags=re.MULTILINE,
    ):
        has_standard_conclusion = bool(re.search(r'因此，答案为', text))
        has_proof_conclusion = bool(
            re.search(r'(所以|因此).*(结论成立|得证|证毕)', text)
            or re.search(r'这就证明了', text)
        )
        if has_standard_conclusion or (allow_proof_conclusion and has_proof_conclusion):
            return True

    return False
