const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/+$/, '') ?? ''

export interface FeedbackPayload {
  user_id: string
  session_id?: string | null
  scope?: 'session' | 'question'
  rating?: number | null
  comment?: string | null
  tags?: string[]
  context?: Record<string, unknown>
}

export async function submitFeedback(payload: FeedbackPayload): Promise<{ status: string; id: number }> {
  const res = await fetch(`${API_BASE}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      scope: 'session',
      tags: [],
      context: {},
      ...payload,
    }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => null) as { detail?: { message?: string } } | null
    throw new Error(data?.detail?.message ?? `HTTP ${res.status}`)
  }
  return res.json()
}
