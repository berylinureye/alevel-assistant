import type {
  AnalyzeRequest,
  ChatQuestionRequest,
  ChatQuestionResponse,
  ExplainQuestionRequest,
  ExplainQuestionResponse,
  HomeworkResponse,
  PageSummary,
  PriorityTopic,
  QuestionResult,
} from '../types'

/**
 * API base URL — 开发时为空（靠 Vite proxy），生产时指向后端服务地址。
 * 通过 Vite 环境变量 VITE_API_BASE_URL 配置。
 */
const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/+$/, '') ?? ''
const IMAGE_EXT_BY_MIME: Record<string, string> = {
  'image/jpeg': '.jpg',
  'image/jpg': '.jpg',
  'image/png': '.png',
  'image/webp': '.webp',
  'image/heic': '.heic',
  'image/heif': '.heif',
  'image/heic-sequence': '.heic',
  'image/heif-sequence': '.heif',
}

function getUploadFilename(file: File): string {
  const name = file.name.trim()
  if (/\.[a-z0-9]+$/i.test(name)) {
    return name
  }

  const normalizedType = file.type.toLowerCase()
  const ext =
    IMAGE_EXT_BY_MIME[normalizedType] ??
    (normalizedType.startsWith('image/') ? '.jpg' : '')

  return `${name || 'upload'}${ext || '.jpg'}`
}

function appendImageFile(form: FormData, file: File) {
  // iOS/Safari may hand back filenames like "image" without an extension.
  form.append('image', file, getUploadFilename(file))
}

function createAbortError(): Error {
  try {
    return new DOMException('分析已取消', 'AbortError')
  } catch {
    const err = new Error('分析已取消')
    err.name = 'AbortError'
    return err
  }
}

export function isAbortError(error: unknown): boolean {
  return (
    error instanceof DOMException
      ? error.name === 'AbortError'
      : error instanceof Error && error.name === 'AbortError'
  )
}

async function readFetchErrorMessage(res: Response): Promise<string> {
  if (res.status === 502 || res.status === 503 || res.status === 504) {
    return '无法连接到后端服务，请确认服务器已启动（python server.py）'
  }
  const data: unknown = await res.json().catch(() => null)
  if (data && typeof data === 'object') {
    const o = data as Record<string, unknown>
    if (typeof o.message === 'string') return o.message
    const detail = o.detail
    if (detail && typeof detail === 'object' && 'message' in detail) {
      const m = (detail as { message?: unknown }).message
      if (typeof m === 'string') return m
    }
    if (typeof detail === 'string') return detail
  }
  return `HTTP ${res.status}`
}

/**
 * 前端埋点：向后端 /feedback/track 发送一个事件。
 * - event_type 必须以 "ui_" 前缀（服务端强制校验）
 * - 失败静默吞掉，绝不影响主流程
 * - 使用 fire-and-forget：不 await，不阻塞调用点
 */
export function trackEvent(
  eventType: string,
  meta?: Record<string, unknown>,
  durationMs = 0,
): void {
  try {
    if (!eventType.startsWith('ui_')) return
    const body = JSON.stringify({
      event_type: eventType,
      duration_ms: Math.max(0, Math.floor(durationMs || 0)),
      meta: meta || {},
    })
    // 优先用 sendBeacon（页面关闭时也能成功发）；否则 fetch keepalive
    if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
      const blob = new Blob([body], { type: 'application/json' })
      if (navigator.sendBeacon(`${API_BASE}/feedback/track`, blob)) return
    }
    void fetch(`${API_BASE}/feedback/track`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
      keepalive: true,
    }).catch(() => {})
  } catch {
    /* noop */
  }
}

/** 将 SSE 文本块解析为完整事件；一个 chunk 可能含多个事件，也可能被截断（由调用方缓冲） */
export function parseSSE(chunk: string): Array<{ event: string; data: string }> {
  const events: Array<{ event: string; data: string }> = []
  const blocks = chunk.split('\n\n')
  for (const block of blocks) {
    if (!block.trim()) continue
    const lines = block.split(/\r?\n/)
    let eventName = ''
    const dataLines: string[] = []
    for (const line of lines) {
      if (line.startsWith('event:')) {
        eventName = line.slice(6).trim()
      } else if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trimStart())
      }
    }
    if (!eventName || dataLines.length === 0) continue
    events.push({ event: eventName, data: dataLines.join('\n') })
  }
  return events
}

export interface AgentProgressData {
  question_number: string
  agent_name?: string
  agent_index?: number
  total_agents?: number
  status?: string  // "started" | "completed" | "voting" | "error"
  [key: string]: unknown
}

export type AgentStepType = 'think' | 'act' | 'observe' | 'decide' | 'final' | (string & {})
export type AgentStepStatus = 'running' | 'completed' | 'failed' | (string & {})

export interface AgentStepData {
  question_number: string
  step_type: AgentStepType
  title: string
  summary: string
  status: AgentStepStatus
  agent_name?: string | null
  tool?: string | null
  detail?: Record<string, unknown>
  confidence?: 'high' | 'medium' | 'low'
  user_visible?: boolean
  severity?: 'info' | 'success' | 'warning' | 'error'
  paper_id?: string | null
  question_id?: string | null
  match_confidence?: 'high' | 'medium' | 'low' | null
  match_source?: 'cover' | 'page_header' | 'question_text' | 'manual' | 'none' | null
  grading_route?: 'past_paper_mark_scheme' | 'open_ai_grading' | null
  needs_user_confirmation?: boolean
  mark_scheme_confidence?: 'high' | 'medium' | 'low' | null
  mark_scheme_context_error?: string | null
}

export interface QuestionExtractedData {
  question_number: string
  question_text: string
  student_answer: string
  working_steps: string[]
  marks?: number
  bbox?: number[]
  page?: number | null
  image_quality?: string
  confidence?: number
  grading_route?: 'past_paper_mark_scheme' | 'open_ai_grading' | null
  mark_scheme_confidence?: 'high' | 'medium' | 'low' | null
  mark_scheme_context_error?: string | null
}

export interface StreamCallbacks {
  onSegmentation: (data: { question_count: number; questions_preview: string[] }) => void
  onQuestion: (question: QuestionResult) => void
  onSummary: (summary: PageSummary) => void
  onError: (message: string) => void
  onDone: () => void
  onAgentProgress?: (data: AgentProgressData) => void
  onAgentStep?: (data: AgentStepData) => void
  onSolution?: (data: { question_number: string; solution_text: string | null }) => void
  onQuestionExtracted?: (data: QuestionExtractedData) => void
}

export interface PrepareUploadResult {
  status: string
  upload_id: string
  question_count: number
}

export async function prepareUpload(
  file: File,
  userHint?: string,
  signal?: AbortSignal,
): Promise<PrepareUploadResult> {
  const form = new FormData()
  appendImageFile(form, file)
  if (userHint?.trim()) form.append('user_hint', userHint.trim())
  const res = await fetch(`${API_BASE}/prepare-upload`, {
    method: 'POST',
    body: form,
    signal,
  })
  if (!res.ok) {
    throw new Error(await readFetchErrorMessage(res))
  }
  return res.json()
}

async function analyzeAllStreaming(
  files: File[],
  callbacks: StreamCallbacks,
  userHint?: string,
  signal?: AbortSignal,
  uploadIds?: Array<string | null | undefined>,
  routeContext?: Pick<AnalyzeRequest, 'upload_intent' | 'paper_code' | 'question_numbers' | 'fast_batch'>,
): Promise<void> {
  // IMPORTANT: all images go in a SINGLE request. Splitting per-image breaks
  // cross-page parent_stem inheritance — Q6(c) on page 2 can't find its Q6
  // stem on page 1 if they're handled by separate segmenter calls.
  if (signal?.aborted) {
    throw createAbortError()
  }

  const form = new FormData()
  for (const file of files) {
    appendImageFile(form, file)
  }
  form.append('feedback_mode', 'student')
  form.append('review_mode', 'auto')
  if (userHint?.trim()) {
    form.append('user_hint', userHint.trim())
  }
  if (routeContext?.upload_intent) {
    form.append('upload_intent', routeContext.upload_intent)
  }
  if (routeContext?.paper_code?.trim()) {
    form.append('paper_code', routeContext.paper_code.trim())
  }
  if (routeContext?.question_numbers?.trim()) {
    form.append('question_numbers', routeContext.question_numbers.trim())
  }
  if (routeContext?.fast_batch) {
    form.append('fast_batch', 'true')
  }
  const ids = (uploadIds ?? []).filter((v): v is string => typeof v === 'string' && v.length > 0)
  if (ids.length > 0) {
    form.append('upload_ids', ids.join(','))
  }

  let res: Response
  try {
    res = await fetch(`${API_BASE}/analyze-homework-stream`, {
      method: 'POST',
      body: form,
      signal,
    })
  } catch {
    if (signal?.aborted) throw createAbortError()
    throw new Error('无法连接到后端服务，请确认服务器已启动（python server.py）')
  }

  if (!res.ok) {
    throw new Error(await readFetchErrorMessage(res))
  }

  const reader = res.body?.getReader()
  if (!reader) {
    throw new Error('无法读取响应流')
  }

  const decoder = new TextDecoder()
  let buffer = ''

  const dispatchParsed = (eventType: string, rawData: string) => {
    let payload: unknown
    try {
      payload = JSON.parse(rawData)
    } catch {
      payload = rawData
    }
    switch (eventType) {
      case 'segmentation':
        callbacks.onSegmentation(
          payload as { question_count: number; questions_preview: string[] },
        )
        break
      case 'question':
        callbacks.onQuestion(payload as QuestionResult)
        break
      case 'summary':
        callbacks.onSummary(payload as PageSummary)
        break
      case 'error': {
        const msg =
          typeof payload === 'object' &&
          payload !== null &&
          'message' in payload &&
          typeof (payload as { message: unknown }).message === 'string'
            ? (payload as { message: string }).message
            : typeof payload === 'string'
              ? payload
              : JSON.stringify(payload)
        callbacks.onError(msg)
        break
      }
      case 'done':
        callbacks.onDone()
        break
      case 'agent_progress':
        callbacks.onAgentProgress?.(payload as AgentProgressData)
        break
      case 'agent_step':
        callbacks.onAgentStep?.(payload as AgentStepData)
        break
      case 'solution':
        callbacks.onSolution?.(payload as { question_number: string; solution_text: string | null })
        break
      case 'question_extracted':
        callbacks.onQuestionExtracted?.(payload as QuestionExtractedData)
        break
      default:
        break
    }
  }

  try {
    while (true) {
      const { done, value } = await reader.read()
      buffer += decoder.decode(value ?? new Uint8Array(0), { stream: !done })

      const parts = buffer.split('\n\n')
      buffer = parts.pop() ?? ''

      for (const part of parts) {
        if (!part.trim()) continue
        const parsed = parseSSE(part + '\n\n')
        for (const { event: eventType, data: rawData } of parsed) {
          dispatchParsed(eventType, rawData)
        }
      }

      if (done) break
    }
  } catch {
    if (signal?.aborted) throw createAbortError()
    throw new Error('与后端的连接中断，请检查后端服务是否仍在运行')
  }

  if (buffer.trim()) {
    const tail = parseSSE(buffer.endsWith('\n\n') ? buffer : buffer + '\n\n')
    for (const { event: eventType, data: rawData } of tail) {
      dispatchParsed(eventType, rawData)
    }
  }
}

export async function analyzeHomeworkStreaming(
  req: AnalyzeRequest,
  callbacks: StreamCallbacks & { onImageStart?: (imageIndex: number, total: number) => void },
  options?: { signal?: AbortSignal },
): Promise<void> {
  const { images, user_hint, upload_ids, upload_intent, paper_code, question_numbers, fast_batch } = req
  const signal = options?.signal
  if (images.length === 0) {
    throw new Error('请至少选择一张图片')
  }
  if (signal?.aborted) {
    throw createAbortError()
  }

  // Tag each question_number with its source image so the UI retains per-image labels.
  // Previously each image went as a separate request (parallel streams), which broke
  // cross-page parent_stem inheritance — e.g. Q6(c) on page 2 could not inherit the
  // "10 marbles, 4 red, 6 blue" stem printed on page 1 because the two pages lived in
  // different segmenter calls. Now all images go in ONE request; we rebuild the prefix
  // from the server-returned `page` field (1-based).
  const totalImages = images.length
  const labelFor = (page: number | null | undefined, fallbackQn: string): string => {
    if (totalImages <= 1) return fallbackQn
    const p = typeof page === 'number' && page >= 1 ? page : 1
    return `图片 ${p} - ${fallbackQn}`
  }

  // Map from raw question_number → prefixed label, so later events (agent_progress,
  // solution, question_extracted) that only carry the raw qnum can still be routed
  // to the card the UI already created.
  const qnumToLabel = new Map<string, string>()

  // Fire onImageStart once per image up front — the UI uses this only to show
  // "第 N 张图开始处理" and the exact order here is cosmetic.
  for (let i = 1; i <= totalImages; i += 1) {
    callbacks.onImageStart?.(i, totalImages)
  }

  const relabel = (qn: string): string => qnumToLabel.get(qn) ?? qn

  const wrappedCallbacks: StreamCallbacks = {
    onSegmentation: callbacks.onSegmentation,
    onQuestionExtracted: (d) => {
      const label = labelFor(d.page ?? null, d.question_number)
      qnumToLabel.set(d.question_number, label)
      callbacks.onQuestionExtracted?.({ ...d, question_number: label })
    },
    onQuestion: (q) => {
      const label = labelFor(q.page ?? null, q.question_number)
      qnumToLabel.set(q.question_number, label)
      callbacks.onQuestion({ ...q, question_number: label })
    },
    onSummary: callbacks.onSummary,
    onAgentProgress: (d) => {
      callbacks.onAgentProgress?.({ ...d, question_number: relabel(d.question_number) })
    },
    onAgentStep: (d) => {
      callbacks.onAgentStep?.({ ...d, question_number: relabel(d.question_number) })
    },
    onSolution: (d) => {
      callbacks.onSolution?.({ ...d, question_number: relabel(d.question_number) })
    },
    onError: callbacks.onError,
    onDone: callbacks.onDone,
  }

  await analyzeAllStreaming(images, wrappedCallbacks, user_hint, signal, upload_ids, {
    upload_intent,
    paper_code,
    question_numbers,
    fast_batch,
  })
}

function mergeTagSummaries(parts: Record<string, number>[]): Record<string, number> {
  const out: Record<string, number> = {}
  for (const p of parts) {
    for (const [k, v] of Object.entries(p)) {
      out[k] = (out[k] ?? 0) + v
    }
  }
  return out
}

function mergePriorityTopics(parts: PriorityTopic[][]): PriorityTopic[] {
  const merged = new Map<string, PriorityTopic>()
  for (const topics of parts) {
    for (const topic of topics ?? []) {
      const key = `${topic.chapter}::${topic.topic}::${topic.subtopic}`
      const existing = merged.get(key)
      if (existing) {
        existing.error_count += topic.error_count ?? 0
        existing.key_formulas = Array.from(
          new Set([...(existing.key_formulas ?? []), ...(topic.key_formulas ?? [])]),
        ).slice(0, 3)
      } else {
        merged.set(key, {
          chapter: topic.chapter ?? '',
          topic: topic.topic ?? '',
          subtopic: topic.subtopic ?? '',
          error_count: topic.error_count ?? 0,
          key_formulas: Array.from(new Set(topic.key_formulas ?? [])).slice(0, 3),
        })
      }
    }
  }
  return [...merged.values()].sort((a, b) => b.error_count - a.error_count)
}

export function mergePageSummaries(parts: PageSummary[]): PageSummary {
  const total_questions = parts.reduce((a, p) => a + p.total_questions, 0)
  const correct_count = parts.reduce((a, p) => a + p.correct_count, 0)
  const incorrect_count = parts.reduce((a, p) => a + p.incorrect_count, 0)
  const unanswered_count = parts.reduce((a, p) => a + (p.unanswered_count ?? 0), 0)
  const common_error_types = [...new Set(parts.flatMap((p) => p.common_error_types ?? []))]
  let overall_teacher_comment: string
  if (incorrect_count === 0 && unanswered_count === 0) {
    overall_teacher_comment = `全部 ${total_questions} 道题均答对，表现优秀。`
  } else {
    const notesParts: string[] = []
    if (incorrect_count > 0) notesParts.push(`${incorrect_count} 道答错`)
    if (unanswered_count > 0) notesParts.push(`${unanswered_count} 道未作答`)
    const pattern =
      common_error_types.length > 0 ? ` 常见错误类型：${common_error_types.join('、')}。` : ''
    overall_teacher_comment = `共 ${total_questions} 道题中有${notesParts.join('、')}。${pattern} 请查看各题反馈了解详情。`
  }
  return {
    total_questions,
    correct_count,
    incorrect_count,
    unanswered_count,
    review_count: parts.reduce((a, p) => a + p.review_count, 0),
    score_total: parts.reduce((a, p) => a + p.score_total, 0),
    full_score_total: parts.reduce((a, p) => a + p.full_score_total, 0),
    common_error_types,
    knowledge_tags_summary: mergeTagSummaries(parts.map((p) => p.knowledge_tags_summary ?? {})),
    estimated_review_minutes: parts.reduce((a, p) => a + (p.estimated_review_minutes ?? 0), 0),
    priority_topics: mergePriorityTopics(parts.map((p) => p.priority_topics ?? [])),
    overall_teacher_comment,
  }
}

function mergeHomeworkResponses(responses: HomeworkResponse[]): HomeworkResponse {
  if (responses.length === 0) {
    throw new Error('没有可合并的分析结果')
  }
  if (responses.length === 1) {
    return responses[0]
  }

  const questions: QuestionResult[] = []
  for (let imgIdx = 0; imgIdx < responses.length; imgIdx++) {
    const r = responses[imgIdx]
    const n = imgIdx + 1
    for (const q of r.questions) {
      questions.push({
        ...q,
        question_number: `图片 ${n} - ${q.question_number}`,
      })
    }
  }

  return {
    status: 'success',
    questions,
    page_summary: mergePageSummaries(responses.map((r) => r.page_summary)),
  }
}

async function postAnalyzeSingle(
  file: File,
  user_hint?: string,
  upload_id?: string | null,
): Promise<HomeworkResponse> {
  const form = new FormData()
  appendImageFile(form, file)
  form.append('feedback_mode', 'student')
  form.append('review_mode', 'auto')
  if (user_hint?.trim()) {
    form.append('user_hint', user_hint.trim())
  }
  if (upload_id) {
    form.append('upload_ids', upload_id)
  }

  const res = await fetch(`${API_BASE}/analyze-homework`, {
    method: 'POST',
    body: form,
  })

  if (!res.ok) {
    throw new Error(await readFetchErrorMessage(res))
  }

  return res.json()
}

export async function analyzeHomework(
  req: AnalyzeRequest,
  onProgress?: (current: number, total: number) => void,
): Promise<HomeworkResponse> {
  const { images, user_hint, upload_ids } = req
  if (images.length === 0) {
    throw new Error('请至少选择一张图片')
  }

  const total = images.length
  const responses: HomeworkResponse[] = []

  for (let i = 0; i < images.length; i++) {
    onProgress?.(i + 1, total)
    const data = await postAnalyzeSingle(images[i], user_hint, upload_ids?.[i] ?? null)
    responses.push(data)
  }

  return mergeHomeworkResponses(responses)
}

export async function explainQuestion(body: ExplainQuestionRequest): Promise<ExplainQuestionResponse> {
  const res = await fetch(`${API_BASE}/explain-question`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!res.ok) {
    throw new Error(await readFetchErrorMessage(res))
  }

  return res.json()
}

export async function chatQuestion(body: ChatQuestionRequest): Promise<ChatQuestionResponse> {
  const res = await fetch(`${API_BASE}/chat-question`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!res.ok) {
    throw new Error(await readFetchErrorMessage(res))
  }

  return res.json()
}

/**
 * 流式追问：回调按事件触发。
 * onChunk(piece)  —— 每次拿到一小段文本（边来边渲染）
 * onDone(final)   —— 最终完整回复（已做 LaTeX 清洗）
 * onError(msg)    —— 失败
 * 返回一个 cancel 函数可中断读取。
 */
export function chatQuestionStream(
  body: ChatQuestionRequest,
  handlers: {
    onChunk: (piece: string) => void
    onDone: (final: string) => void
    onError: (msg: string) => void
  },
): () => void {
  const controller = new AbortController()

  void (async () => {
    try {
      const res = await fetch(`${API_BASE}/chat-question/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      })
      if (!res.ok || !res.body) {
        handlers.onError(await readFetchErrorMessage(res))
        return
      }
      const reader = res.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let buf = ''
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        // SSE 事件以 \n\n 分隔
        let sepIdx: number
        while ((sepIdx = buf.indexOf('\n\n')) !== -1) {
          const rawEvent = buf.slice(0, sepIdx)
          buf = buf.slice(sepIdx + 2)
          const lines = rawEvent.split('\n')
          let event = 'message'
          let dataLine = ''
          for (const line of lines) {
            if (line.startsWith('event:')) event = line.slice(6).trim()
            else if (line.startsWith('data:')) dataLine += line.slice(5).trim()
          }
          if (!dataLine) continue
          try {
            const obj = JSON.parse(dataLine)
            if (event === 'chunk' && typeof obj.text === 'string') {
              handlers.onChunk(obj.text)
            } else if (event === 'done') {
              handlers.onDone(typeof obj.final === 'string' ? obj.final : '')
              return
            } else if (event === 'error') {
              handlers.onError(String(obj.message || '流式回复失败'))
              return
            }
          } catch {
            /* ignore malformed SSE frame */
          }
        }
      }
      // 理论上应该先收到 done；走到这里说明流提前关闭，但有可能已经 onDone
    } catch (err) {
      if ((err as { name?: string })?.name === 'AbortError') return
      handlers.onError((err as Error)?.message || '网络错误')
    }
  })()

  return () => controller.abort()
}
