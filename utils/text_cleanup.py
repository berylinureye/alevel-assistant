"""
Strip LaTeX and Markdown artifacts from LLM output to produce clean plain text.

Used as a post-processing step on all feedback fields so that students and teachers
see readable text without raw $\\frac{a}{b}$ or **bold** markers.
"""
from __future__ import annotations

import re


def strip_latex_and_markdown(text: str) -> str:
    """Convert LLM output with LaTeX/Markdown into clean plain text.

    Handles:
    - $...$ and $$...$$ delimiters → removed, content kept
    - \\frac{a}{b} → a/b
    - \\bar{x} → x̄  (common stats symbol)
    - \\sum → Σ, \\int → ∫, \\sqrt → √, \\times → ×, \\cdot → ·
    - x^{2} or x^2 → x²  (common superscripts)
    - x_{i} or x_i → xi  (subscripts simplified)
    - Markdown headers ### → removed
    - **bold** and *italic* → plain text
    - Escaped braces \\{ \\} → { }
    """
    if not text:
        return text

    s = text

    # Remove $$ and $ delimiters (keep inner content)
    s = s.replace("$$", "")
    s = re.sub(r'\$([^$]*)\$', r'\1', s)
    # Catch any remaining lone $
    s = s.replace("$", "")

    # \\frac{a}{b} → (a)/(b)
    s = re.sub(r'\\frac\s*\{([^}]*)\}\s*\{([^}]*)\}', r'(\1)/(\2)', s)
    # \\bar{x} → x̄
    s = re.sub(r'\\bar\s*\{([^}]*)\}', r'\1̄', s)
    # \\hat{x} → x̂
    s = re.sub(r'\\hat\s*\{([^}]*)\}', r'\1̂', s)
    # \\sqrt{x} → √(x)
    s = re.sub(r'\\sqrt\s*\{([^}]*)\}', r'√(\1)', s)
    # \\text{...} → just the text
    s = re.sub(r'\\text\s*\{([^}]*)\}', r'\1', s)
    # \\mathrm{...} → just the text
    s = re.sub(r'\\mathrm\s*\{([^}]*)\}', r'\1', s)
    # \\left and \\right → removed
    s = re.sub(r'\\(left|right)\s*', '', s)

    # Common symbol replacements
    _symbols = {
        r'\sum': 'Σ',
        r'\int': '∫',
        r'\times': '×',
        r'\cdot': '·',
        r'\pm': '±',
        r'\leq': '≤',
        r'\geq': '≥',
        r'\neq': '≠',
        r'\approx': '≈',
        r'\infty': '∞',
        r'\sigma': 'σ',
        r'\mu': 'μ',
        r'\alpha': 'α',
        r'\beta': 'β',
        r'\theta': 'θ',
        r'\pi': 'π',
        r'\lambda': 'λ',
        r'\Delta': 'Δ',
        r'\partial': '∂',
        r'\forall': '∀',
        r'\exists': '∃',
        r'\in': '∈',
        r'\quad': ' ',
        r'\qquad': '  ',
        r'\,': ' ',
        r'\;': ' ',
        r'\!': '',
    }
    for latex, plain in _symbols.items():
        s = s.replace(latex, plain)

    # Superscripts: x^{2} → x², x^2 → x²
    _superscripts = {'0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
                     '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
                     'n': 'ⁿ', '-': '⁻'}
    def _sup_replace(m):
        content = m.group(1)
        return ''.join(_superscripts.get(c, f'^{c}') for c in content)
    s = re.sub(r'\^\{([^}]*)\}', _sup_replace, s)
    s = re.sub(r'\^(\d)', lambda m: _superscripts.get(m.group(1), f'^{m.group(1)}'), s)

    # Subscripts: x_{i} → x_i (just remove braces)
    s = re.sub(r'_\{([^}]*)\}', r'_\1', s)

    # Escaped braces
    s = s.replace(r'\{', '{').replace(r'\}', '}')

    # Remove remaining backslash-commands (e.g. \operatorname, \displaystyle)
    s = re.sub(r'\\[a-zA-Z]+\s*', '', s)

    # Markdown: ### headers → remove the hashes
    s = re.sub(r'^#{1,6}\s+', '', s, flags=re.MULTILINE)
    # **bold** → plain
    s = re.sub(r'\*\*([^*]+)\*\*', r'\1', s)
    # *italic* → plain
    s = re.sub(r'\*([^*]+)\*', r'\1', s)
    # `code` → plain
    s = re.sub(r'`([^`]+)`', r'\1', s)

    # Clean up extra whitespace
    s = re.sub(r'  +', ' ', s)
    s = re.sub(r'\n{3,}', '\n\n', s)
    s = s.strip()

    return s
