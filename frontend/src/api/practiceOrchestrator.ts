import type {
  PracticeRecommendationRequest,
  PracticeRecommendationResponse,
} from '../types/practice'

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/+$/, '') ?? ''

function getErrorMessage(data: unknown, fallback: string): string {
  if (!data || typeof data !== 'object') return fallback

  const payload = data as Record<string, unknown>
  if (typeof payload.message === 'string') return payload.message
  if (typeof payload.detail === 'string') return payload.detail

  const detail = payload.detail
  if (detail && typeof detail === 'object' && 'message' in detail) {
    const message = (detail as { message?: unknown }).message
    if (typeof message === 'string') return message
  }

  return fallback
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const data = await res.json().catch(() => null)
    throw new Error(getErrorMessage(data, `HTTP ${res.status}`))
  }
  return res.json()
}

export async function recommendPractice(
  body: PracticeRecommendationRequest,
): Promise<PracticeRecommendationResponse> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}/practice-orchestrator/recommendations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch (error) {
    throw new Error(error instanceof Error && error.message ? error.message : 'Network request failed')
  }
  return handleResponse(res)
}
