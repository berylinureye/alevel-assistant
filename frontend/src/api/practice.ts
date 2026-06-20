/** 题库练习模式 API 客户端 */

import type {
  RandomQuestionRequest,
  RandomQuestionResponse,
  SubmitAnswerRequest,
  SubmitAnswerResponse,
  TopicStats,
  QuestionBankStats,
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

export async function fetchRandomQuestions(params: RandomQuestionRequest): Promise<RandomQuestionResponse> {
  const res = await fetch(`${API_BASE}/questions/random`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  return handleResponse(res)
}

export async function submitAnswer(body: SubmitAnswerRequest): Promise<SubmitAnswerResponse> {
  const res = await fetch(`${API_BASE}/questions/submit-answer`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return handleResponse(res)
}

export async function fetchTopics(): Promise<TopicStats[]> {
  const res = await fetch(`${API_BASE}/questions/meta/topics`)
  return handleResponse(res)
}

export interface TaxonomySubtopic {
  key: string
  name: string
  name_cn: string
  subtopics: string[]
}

export interface TaxonomyPaper {
  paper_num: number
  paper_name: string
  level: string
  component: string
  topics: TaxonomySubtopic[]
}

export interface TaxonomyResponse {
  status: string
  difficulty_levels: Record<string, { label: string; range: [number, number]; description: string }>
  papers: TaxonomyPaper[]
}

export async function fetchTaxonomy(paperNum?: number): Promise<TaxonomyResponse> {
  const url = paperNum
    ? `${API_BASE}/questions/meta/taxonomy?paper_num=${paperNum}`
    : `${API_BASE}/questions/meta/taxonomy`
  const res = await fetch(url)
  return handleResponse(res)
}

export interface PaperListItem {
  id: number
  subject_code: string
  year: number
  session: string
  paper_num: number
  paper_name: string
  level: string
  component: string
  variant: number
  has_qp: boolean
  has_ms: boolean
}

export interface PaperListResponse {
  status: string
  count: number
  papers: PaperListItem[]
}

export async function fetchPapers(params?: {
  paper_num?: number
  year?: number
  session?: string
  level?: string
}): Promise<PaperListResponse> {
  const searchParams = new URLSearchParams()
  if (params?.paper_num) searchParams.set('paper_num', String(params.paper_num))
  if (params?.year) searchParams.set('year', String(params.year))
  if (params?.session) searchParams.set('session', params.session)
  if (params?.level) searchParams.set('level', params.level)
  const qs = searchParams.toString()
  const res = await fetch(`${API_BASE}/questions/papers${qs ? `?${qs}` : ''}`)
  return handleResponse(res)
}

export function getPaperDownloadUrl(paperId: number, fileType: 'qp' | 'ms'): string {
  return `${API_BASE}/questions/papers/${paperId}/download/${fileType}`
}

export async function fetchStats(): Promise<QuestionBankStats> {
  const res = await fetch(`${API_BASE}/questions/meta/stats`)
  return handleResponse(res)
}

export async function exportQuestions(params: RandomQuestionRequest): Promise<RandomQuestionResponse> {
  const res = await fetch(`${API_BASE}/questions/export`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  return handleResponse(res)
}
