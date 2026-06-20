import { useState } from 'react'
import { submitFeedback } from '../api/feedback'
import { getAnonymousUserId } from '../lib/userId'
import { loadProfile } from '../lib/profile'

const QUICK_TAGS = [
  { key: 'accurate', label: '批改准确' },
  { key: 'helpful', label: '讲解有帮助' },
  { key: 'fast', label: '速度快' },
  { key: 'wrong_grading', label: '批改错误' },
  { key: 'unclear', label: '讲解看不懂' },
  { key: 'slow', label: '太慢' },
  { key: 'format', label: '格式混乱' },
  { key: 'ocr_error', label: '识别错误' },
]

export interface FeedbackPanelProps {
  sessionId?: string | null
  context?: Record<string, unknown>
}

export function FeedbackPanel({ sessionId, context }: FeedbackPanelProps) {
  const [rating, setRating] = useState<number | null>(null)
  const [hoverRating, setHoverRating] = useState<number | null>(null)
  const [comment, setComment] = useState('')
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const toggleTag = (tag: string) => {
    setSelectedTags((prev) => (prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]))
  }

  const handleSubmit = async () => {
    if (rating == null && selectedTags.length === 0 && !comment.trim()) {
      setError('请至少选择评分、标签或写一段反馈')
      return
    }
    setError(null)
    setSubmitting(true)
    try {
      const profile = loadProfile()
      const mergedContext = {
        ...(context ?? {}),
        ...(profile
          ? {
              profile_name: profile.name,
              profile_phone: profile.phone,
              profile_grade: profile.grade,
            }
          : {}),
      }
      await submitFeedback({
        user_id: profile?.phone || getAnonymousUserId(),
        session_id: sessionId ?? null,
        scope: 'session',
        rating,
        comment: comment.trim() || null,
        tags: selectedTags,
        context: mergedContext,
      })
      setSubmitted(true)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setSubmitting(false)
    }
  }

  if (submitted) {
    return (
      <div className="rounded-lg border border-green-200 bg-green-50 p-4 text-sm text-green-800">
        感谢你的反馈！🎉 我们会根据你的建议持续改进。
      </div>
    )
  }

  const shownRating = hoverRating ?? rating

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <h3 className="text-sm font-semibold text-gray-900">本次批改怎么样？</h3>
      <p className="mt-1 text-xs text-gray-500">
        你的反馈会帮助我们改进 AI 批改质量。前往「个人」填写姓名和手机号后，反馈会带上你的身份信息，便于我们回复你；否则匿名提交。
      </p>

      <div className="mt-3 flex items-center gap-1" role="radiogroup" aria-label="评分">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            aria-label={`${n} 星`}
            onMouseEnter={() => setHoverRating(n)}
            onMouseLeave={() => setHoverRating(null)}
            onClick={() => setRating(n)}
            className="text-2xl leading-none transition"
            style={{ color: shownRating != null && n <= shownRating ? '#f59e0b' : '#d1d5db' }}
          >
            ★
          </button>
        ))}
        {rating != null ? (
          <span className="ml-2 text-xs text-gray-500">{rating} / 5</span>
        ) : null}
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {QUICK_TAGS.map((t) => {
          const active = selectedTags.includes(t.key)
          return (
            <button
              key={t.key}
              type="button"
              onClick={() => toggleTag(t.key)}
              className={`rounded-full border px-2.5 py-1 text-xs transition ${
                active
                  ? 'border-blue-500 bg-blue-50 text-blue-600'
                  : 'border-gray-200 bg-white text-gray-600 hover:bg-gray-50'
              }`}
            >
              {t.label}
            </button>
          )
        })}
      </div>

      <textarea
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        placeholder="想说点什么？（可选，最多 2000 字）"
        maxLength={2000}
        rows={3}
        className="mt-3 w-full rounded-md border border-gray-200 px-3 py-2 text-sm outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-200"
      />

      {error ? <p className="mt-2 text-xs text-red-600">{error}</p> : null}

      <div className="mt-3 flex justify-end">
        <button
          type="button"
          onClick={handleSubmit}
          disabled={submitting}
          className="rounded-md bg-blue-600 px-4 py-1.5 text-sm font-medium text-white transition hover:bg-blue-700 disabled:opacity-50"
        >
          {submitting ? '提交中…' : '提交反馈'}
        </button>
      </div>
    </div>
  )
}
