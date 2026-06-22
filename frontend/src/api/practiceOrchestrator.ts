import type {
  PracticeRecommendationRequest,
  PracticeRecommendationResponse,
} from '../types/practice'

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/+$/, '') ?? ''

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const data = await res.json().catch(() => null)
    const msg = data?.detail ?? data?.message ?? `HTTP ${res.status}`
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
  }
  return res.json()
}

export async function recommendPractice(
  body: PracticeRecommendationRequest,
): Promise<PracticeRecommendationResponse> {
  const res = await fetch(`${API_BASE}/practice-orchestrator/recommendations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return handleResponse(res)
}
