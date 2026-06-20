import katex from 'katex'

/**
 * Render inline LaTeX ($...$) in a text string to HTML using KaTeX.
 * Falls back to the raw string on error.
 */
export function renderLatex(text: string): string {
  return text.replace(/\$([^$]+)\$/g, (_match, tex: string) => {
    try {
      return katex.renderToString(tex, { throwOnError: false, displayMode: false })
    } catch {
      return `$${tex}$`
    }
  })
}
