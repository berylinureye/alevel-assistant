import katex from 'katex'

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function tryKatex(tex: string, displayMode = false): string | null {
  const t = tex.trim()
  if (!t) return null
  try {
    return katex.renderToString(t, {
      output: 'html',
      throwOnError: true,
      strict: 'ignore',
      displayMode,
    })
  } catch {
    return null
  }
}

function replaceSqrt(input: string): string {
  let text = input
  let prev = ''
  while (text !== prev) {
    prev = text
    text = text.replace(/sqrt\(([^()]+)\)/gi, '\\sqrt{$1}')
  }
  return text
}

function replaceInverseTrig(input: string): string {
  return input.replace(
    /\b(sin|cos|tan)\s*\^\s*\{?\s*(-?1)\s*\}?\s*\(([^()]+)\)/gi,
    (_match, fn: string, power: string, inner: string) =>
      `\\${fn}^{${power}}\\left(${inner.trim()}\\right)`,
  )
}

function replaceTrig(input: string): string {
  return input.replace(
    /\b(sin|cos|tan|log|ln)\s*\(([^()]+)\)/gi,
    (_match, fn: string, inner: string) => `\\${fn}\\left(${inner.trim()}\\right)`,
  )
}

function replacePi(input: string): string {
  return input.replace(/\bpi\b/gi, '\\pi')
}

function replaceSimpleFractions(input: string): string {
  let text = input
  let prev = ''
  const token =
    '(?:-?(?:\\\\sqrt\\{[^{}]+\\}|\\\\pi|\\\\[a-zA-Z]+\\^\\{[^{}]+\\}\\\\left\\([^()]+\\\\right\\)|\\\\[a-zA-Z]+\\\\left\\([^()]+\\\\right\\)|[a-zA-Z][a-zA-Z0-9]*|\\d+(?:\\.\\d+)?|\\([^()]+\\)))'

  while (text !== prev) {
    prev = text
    text = text.replace(new RegExp(`(${token})\\s*\\/\\s*(${token})`, 'g'), '\\frac{$1}{$2}')
  }

  return text
}

/** 将常见 ASCII 写法增强为更易被 KaTeX 解析的形式 */
function autoEnhance(s: string): string {
  let text = s
    .replace(/(?<!\\)\b(sin|cos|tan|log|ln)(?=\s*[\^\\])/gi, '\\$1')
    .replace(/\bdy\s*\/\s*dx\b/gi, '\\frac{dy}{dx}')
    .replace(/\bd\s*\/\s*dx\b/gi, '\\frac{d}{dx}')
    .replace(/([a-zA-Z0-9)\]}])\^(-?\d+)/g, '$1^{$2}')
    .replace(/([a-zA-Z0-9)\]}])\^\{([^}]+)\}/g, '$1^{$2}')

  text = replaceSqrt(text)
  text = replaceInverseTrig(text)
  text = replaceTrig(text)
  text = replacePi(text)
  text = replaceSimpleFractions(text)
  return text
}

/**
 * $...$ 内的内容按行内公式渲染；外侧段落也做 token-level 自动渲染，
 * 确保 `$...$` 之间的裸 LaTeX（如 \frac、\left…\right）也能正常显示。
 */
function renderDollarDelimited(text: string): string {
  const parts: string[] = []
  let pos = 0
  const re = /\$([^$]+)\$/g
  let m: RegExpExecArray | null
  while ((m = re.exec(text)) !== null) {
    const gap = text.slice(pos, m.index)
    parts.push(renderSegmentAuto(gap))
    const inner = m[1].trim()
    const html = tryKatex(inner, false) ?? escapeHtml(m[0])
    parts.push(html)
    pos = m.index + m[0].length
  }
  parts.push(renderSegmentAuto(text.slice(pos)))
  return parts.join('')
}

/** 对一段不含 $ 分隔符的文本做 token-level 自动数学渲染 */
function renderSegmentAuto(segment: string): string {
  if (!segment) return ''
  if (!hasAutoMathHint(segment)) return escapeHtml(segment)

  const enhanced = autoEnhance(segment)
  let last = 0
  let out = ''
  let found = false
  const re = new RegExp(MATH_TOKEN_RE.source, 'gi')
  let m2: RegExpExecArray | null
  while ((m2 = re.exec(enhanced)) !== null) {
    found = true
    out += escapeHtml(enhanced.slice(last, m2.index))
    const rawToken = m2[0]
    const piece = autoEnhance(rawToken)
    const html = tryKatex(piece, false) ?? escapeHtml(rawToken)
    out += html
    last = m2.index + m2[0].length
  }
  if (found) {
    out += escapeHtml(enhanced.slice(last))
    return out
  }
  return escapeHtml(segment)
}

/** 与常见数学片段匹配的 token（较长模式在前） */
const MATH_TOKEN_RE =
  /(\\(?:sin|cos|tan|log|ln)\^\{[^}]+\}\\left[([{][^)\]}\n]*\\right[)\]}]|\\(?:sin|cos|tan|log|ln)\\left[([{][^)\]}\n]*\\right[)\]}]|\\frac\{[^}]+\}\{[^}]+\}|\\sqrt\{[^}]+\}|\\left[([{][^)\]}\n]*\\right[)\]}]|\\[a-zA-Z]+\^\{[^}]+\}|\\int|\\sum|\\prod|\\lim|\\sin|\\cos|\\tan|\\log|\\ln|\\exp|\\pi|\\infty|\\partial|(?:sin|cos|tan)\s*\^\s*-?1\s*\([^)\n]+\)|(?:sin|cos|tan|log|ln)\s*\([^)\n]+\)|sqrt\([^)\n]+\)|[a-zA-Z]+\^(?:-?\d+|\{[^}]+\})|(?:-?(?:pi|sqrt\([^)\n]+\)|[a-zA-Z0-9]+)\s*\/\s*(?:pi|sqrt\([^)\n]+\)|[a-zA-Z0-9]+))|(?:[a-zA-Z0-9(){}\\^]+(?:\s*[=+\-*/]\s*[a-zA-Z0-9(){}\\^]+)+)|dy\s*\/\s*dx|d\s*\/\s*dx)/gi

function hasAutoMathHint(text: string): boolean {
  return (
    /\\(frac|sqrt|int|sum|prod|lim|left|right|sin|cos|tan|log|ln|pi|triangle|circ|angle|perp|parallel|alpha|beta|gamma|theta|lambda|sigma|phi|omega|infty|cdot|times|geq|leq|neq|approx|pm|therefore)\b/.test(text) ||
    /\b(?:sin|cos|tan|log|ln)\s*\(/i.test(text) ||
    /\b(?:sin|cos|tan)\s*\^\s*-?1\s*\(/i.test(text) ||
    /\bsqrt\(/i.test(text) ||
    /\bpi\b/i.test(text) ||
    /[a-zA-Z0-9)\]}]\^-?\d+/.test(text) ||
    /\^\{/.test(text) ||
    /[=+\-/*]/.test(text)
  )
}

function renderLineNoDollar(line: string): string {
  const trimmed = line.trim()
  if (!trimmed) return ''

  const enhanced = autoEnhance(line)

  let last = 0
  let out = ''
  let found = false
  const re = new RegExp(MATH_TOKEN_RE.source, 'gi')
  let m: RegExpExecArray | null
  while ((m = re.exec(enhanced)) !== null) {
    found = true
    out += escapeHtml(enhanced.slice(last, m.index))
    const rawToken = m[0]
    const piece = autoEnhance(rawToken)
    const html = tryKatex(piece, false) ?? escapeHtml(rawToken)
    out += html
    last = m.index + m[0].length
  }
  if (found) {
    out += escapeHtml(enhanced.slice(last))
    return out
  }

  return escapeHtml(line)
}

function renderAutoOrPlain(text: string): string {
  if (!text.includes('\n')) {
    return renderLineNoDollar(text)
  }
  return text.split('\n').map((line) => (line === '' ? '' : renderLineNoDollar(line))).join('<br>\n')
}

/**
 * 将题目/答案等文本中的数学式渲染为 KaTeX HTML。
 * - 含 `$...$` 时仅处理美元对，外侧转义（后端约定用 $ 标记数学）
 * - 无 `$` 时默认按纯文本转义，避免把英文句子误当成公式（丢失空格、全斜体）
 * - 可选：仅当存在明确 LaTeX 命令时尝试旧版自动渲染，兼容未加 $ 的历史数据
 */
/**
 * 把 `\( ... \)` 转成 `$...$`，`\[ ... \]` 转成 `$$...$$`。
 * LLM（尤其是 qwen/glm 系列）有时会输出这种 TeX 分隔符，KaTeX 本身不认，
 * 统一成美元符后走已有的美元分隔渲染管线。
 */
function normalizeLatexDelimiters(text: string): string {
  return text
    // \[ ... \]  → $$ ... $$（多行也匹配）
    .replace(/\\\[([\s\S]+?)\\\]/g, (_m, inner: string) => `$${inner}$`)
    // \( ... \)  → $ ... $
    .replace(/\\\(([\s\S]+?)\\\)/g, (_m, inner: string) => `$${inner}$`)
}

export function renderMath(text: string): string {
  if (text == null || text === '') return ''
  // 先把 TeX 风格的 \(...\) / \[...\] 分隔符转成 $...$，再走既有渲染
  const normalized = (text.includes('\\(') || text.includes('\\['))
    ? normalizeLatexDelimiters(text)
    : text
  if (normalized.includes('$')) {
    try {
      return renderDollarDelimited(normalized)
    } catch {
      return escapeHtml(normalized)
    }
  }
  if (hasAutoMathHint(normalized)) {
    try {
      return renderAutoOrPlain(normalized)
    } catch {
      return escapeHtml(normalized)
    }
  }
  return escapeHtml(normalized)
}
