"""
LaTeX 后处理：把 `\\frac{a}{b}` / `\\dfrac{a}{b}` / `\\tfrac{a}{b}` 中
**纯整数**的分数约到最简。

只处理能稳定识别为"整数/整数"的情形：
- 含变量、根号、希腊字母、其他 LaTeX 命令的分子/分母一律跳过
- 已经最简（gcd=1 且无需挪符号）的原样返回
- 约掉公因子后分母为 1 → 直接返回整数
- 负号统一到分子外：`-\\frac{|p|}{q}`

依赖 sympy（项目里已有 requirements）。失败时静默返回原字符串，不抛异常。
"""
from __future__ import annotations

import re

from sympy import Rational

# 匹配 \frac{A}{B} / \dfrac{...} / \tfrac{...}
# 分子/分母各自用一层非贪婪的 [^{}]* —— 只处理平铺整数，嵌套花括号直接放行。
_FRAC_RE = re.compile(r"\\(d?frac|tfrac)\{([^{}]+)\}\{([^{}]+)\}")

# 分子 / 分母必须是可能带前缀负号的整数字面量
_INT_RE = re.compile(r"^\s*-?\d+\s*$")


def _render(cmd: str, num: int, den: int) -> str:
    # den > 0 恒成立（Rational 规范化时会把符号移到分子）
    if den == 1:
        return str(num)
    if num < 0:
        return f"-\\{cmd}{{{-num}}}{{{den}}}"
    return f"\\{cmd}{{{num}}}{{{den}}}"


def _reduce(match: re.Match[str]) -> str:
    cmd, num_raw, den_raw = match.group(1), match.group(2), match.group(3)
    if not _INT_RE.match(num_raw) or not _INT_RE.match(den_raw):
        return match.group(0)
    try:
        n = int(num_raw.strip())
        d = int(den_raw.strip())
        if d == 0:
            return match.group(0)
        r = Rational(n, d)
        reduced = _render(cmd, int(r.p), int(r.q))
    except Exception:  # noqa: BLE001
        return match.group(0)

    # 约分后等价于原串就原样返回，避免无意义改写
    if reduced == match.group(0):
        return match.group(0)
    return reduced


def simplify_latex_fractions(text: str) -> str:
    """约简 text 中所有纯整数 LaTeX 分数。非整数或解析失败时原样返回。"""
    if not text or "\\" not in text:
        return text
    return _FRAC_RE.sub(_reduce, text)
