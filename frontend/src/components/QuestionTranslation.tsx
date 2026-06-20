import { useState } from 'react'
import { renderMath } from '../utils/mathRender'

interface QuestionTranslationProps {
  questionText: string
}

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/+$/, '') ?? ''

export function QuestionTranslation({ questionText }: QuestionTranslationProps) {
  const [open, setOpen] = useState(false)
  const [translation, setTranslation] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleToggle = async () => {
    if (open) {
      setOpen(false)
      return
    }
    setOpen(true)
    if (translation != null) return

    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/translate-question`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question_text: questionText }),
      })
      if (!res.ok) throw new Error('翻译请求失败')
      const data = await res.json()
      setTranslation(data.translation)
    } catch (err) {
      setError(err instanceof Error ? err.message : '翻译失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="border-b border-gray-100">
      <button
        type="button"
        onClick={() => void handleToggle()}
        className="flex w-full items-center gap-2 px-4 py-2.5 text-left text-xs font-medium text-blue-700 transition hover:bg-blue-50/50"
      >
        <span className="text-sm">🌐</span>
        <span>{open ? '收起翻译' : '翻译题目'}</span>
        <span className={`ml-auto text-gray-400 transition-transform text-xs ${open ? 'rotate-180' : ''}`}>▼</span>
      </button>

      {open ? (
        <div className="px-4 pb-3">
          {loading && translation == null ? (
            <div className="flex items-center gap-2 py-3 text-xs text-gray-500">
              <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-gray-300 border-t-gray-600" />
              正在翻译…
            </div>
          ) : error != null ? (
            <div className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">{error}</div>
          ) : translation != null ? (
            <div
              className="rounded-lg bg-blue-50/60 border border-blue-100 px-3 py-2.5 text-sm leading-relaxed text-gray-800 whitespace-pre-wrap [&_.katex]:text-inherit"
              dangerouslySetInnerHTML={{ __html: renderMath(translation) }}
            />
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
