"""
多Agent并行数学解题系统 — 答案提取、归一化、投票逻辑
"""
from __future__ import annotations

import re
from collections import Counter
from fractions import Fraction
from typing import Optional


def extract_answer(text: str) -> Optional[str]:
    """
    从模型输出中提取 ANSWER: xxx 的数值部分。
    返回原始字符串（未归一化），或 None。
    """
    if not text:
        return None

    # 匹配 "ANSWER:" 后面的内容（到行尾或下一个换行）
    # 支持中英文冒号
    pattern = r"ANSWER\s*[:：]\s*(.+)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        raw = match.group(1).strip()
        # 清理末尾可能的标点
        raw = raw.rstrip("。.，,；;")
        # 如果答案中有多余文字，只取第一个数学表达式
        # 但保留分数、负号、小数
        return raw.strip()

    # 回退：尝试找第一行的纯数字
    first_line = text.strip().split("\n")[0].strip()
    if re.match(r"^-?\d+(\.\d+)?(/\d+)?$", first_line):
        return first_line

    return None


def normalize_answer(raw: str) -> str:
    """
    将答案归一化为标准形式，便于比较。
    - 去除多余空白、$、LaTeX 包裹
    - 分数 → 最简分数字符串
    - 小数如果是精确分数则转为分数
    - 整数保持整数
    """
    if not raw:
        return ""

    s = raw.strip()

    # 去除 LaTeX 包裹
    s = s.replace("$", "").replace("\\", "").strip()
    # 去除 \frac{a}{b} → a/b
    frac_match = re.match(r"frac\{(-?\d+)\}\{(\d+)\}", s)
    if frac_match:
        s = f"{frac_match.group(1)}/{frac_match.group(2)}"
    # 去除 \dfrac 同理
    dfrac_match = re.match(r"dfrac\{(-?\d+)\}\{(\d+)\}", s)
    if dfrac_match:
        s = f"{dfrac_match.group(1)}/{dfrac_match.group(2)}"

    # 去除逗号（千分位）
    s = s.replace(",", "").replace(" ", "")

    # 尝试解析为 Fraction 做精确比较
    try:
        frac = Fraction(s).limit_denominator(10**9)
        if frac.denominator == 1:
            return str(frac.numerator)
        return str(frac)
    except (ValueError, ZeroDivisionError):
        pass

    # 尝试解析为 float 再转 Fraction
    try:
        f = float(s)
        frac = Fraction(f).limit_denominator(10**6)
        if frac.denominator == 1:
            return str(frac.numerator)
        # 如果是很简洁的分数，返回分数形式
        if frac.denominator <= 1000:
            return str(frac)
        # 否则返回原始小数
        return s
    except ValueError:
        pass

    # 无法解析，返回清理后的原始字符串
    return s


def answers_equivalent(a: str, b: str) -> bool:
    """判断两个归一化答案是否等价"""
    if a == b:
        return True

    # 尝试数值比较
    try:
        fa = Fraction(a).limit_denominator(10**9)
        fb = Fraction(b).limit_denominator(10**9)
        return fa == fb
    except (ValueError, ZeroDivisionError):
        pass

    try:
        return abs(float(a) - float(b)) < 1e-9
    except ValueError:
        pass

    return False


def vote(answers: list[tuple[str, str, str]]) -> tuple[str, str, str]:
    """
    投票逻辑。

    参数:
        answers: [(agent_name, raw_answer, normalized_answer), ...]

    返回:
        (winning_answer_normalized, confidence, method)
        confidence: "high" / "medium" / "low"
        method: "majority_vote" / "unanimous" / "arbitration_needed"
    """
    valid = [(name, raw, norm) for name, raw, norm in answers if norm]

    if len(valid) == 0:
        return ("", "low", "no_answers")

    if len(valid) == 1:
        return (valid[0][2], "low", "single_answer")

    # 将等价的答案分组
    groups: list[list[tuple[str, str, str]]] = []
    for entry in valid:
        placed = False
        for group in groups:
            if answers_equivalent(entry[2], group[0][2]):
                group.append(entry)
                placed = True
                break
        if not placed:
            groups.append([entry])

    # 按组大小排序
    groups.sort(key=lambda g: len(g), reverse=True)

    if len(groups) == 1:
        # 全部一致
        return (groups[0][0][2], "high", "unanimous")

    if len(groups[0]) >= 2:
        # 多数一致（至少 2 票）
        return (groups[0][0][2], "high", "majority_vote")

    # 三个全不同，需要仲裁
    return ("", "low", "arbitration_needed")
