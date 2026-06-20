export type AgentStepTone = 'info' | 'success' | 'warning' | 'error'
export type AgentStepStatusKind = 'running' | 'completed' | 'failed'

export interface AgentStepInput {
  question_number?: string
  step_type?: string
  title?: string
  summary?: string
  status?: string
  agent_name?: string | null
  tool?: string | null
  confidence?: 'high' | 'medium' | 'low' | string | null
  user_visible?: boolean
  severity?: AgentStepTone | string
  paper_id?: string | null
  question_id?: string | null
  match_confidence?: 'high' | 'medium' | 'low' | string | null
  match_source?: 'cover' | 'page_header' | 'question_text' | 'manual' | 'none' | string | null
  grading_route?: 'past_paper_mark_scheme' | 'open_ai_grading' | string | null
  needs_user_confirmation?: boolean
  mark_scheme_confidence?: 'high' | 'medium' | 'low' | string | null
  mark_scheme_context_error?: string | null
}

export interface AgentStepBadge {
  label: string
  tone: AgentStepTone
}

export interface AgentStepViewModel {
  questionNumber: string
  phaseLabel: string
  title: string
  summary: string
  status: AgentStepStatusKind
  agentName: string | null
  tool: string | null
  badges: AgentStepBadge[]
  fallbackReason: string | null
}

const CONFIDENCE_LABELS: Record<string, string> = {
  high: '高',
  medium: '中',
  low: '低',
}

const MATCH_SOURCE_LABELS: Record<string, string> = {
  cover: '封面',
  page_header: '页眉',
  question_text: '题干',
  manual: '手动确认',
  none: '未匹配',
}

const AGENT_LABELS: Record<string, string> = {
  'Upload Router': '上传路由',
  'Paper Resolver': '真题匹配',
  'Mark Scheme Router': '评分规则检查',
}

const TOOL_LABELS: Record<string, string> = {
  'papers_catalog.csv': '本地题库',
}

function cleanText(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function normalizeStatus(status: unknown): AgentStepStatusKind {
  if (status === 'completed') return 'completed'
  if (status === 'failed') return 'failed'
  return 'running'
}

export function normalizeAgentStepTitle(title: unknown): string {
  const raw = normalizeAgentStepText(title)
  if (!raw) return ''
  return raw
}

function normalizeAgentStepText(value: unknown): string {
  const raw = cleanText(value)
  if (!raw) return ''
  return raw
    .replace(/\bPast Paper\b/g, '真题')
    .replace(/\bpaper\b/gi, '卷子')
    .replace(/\bmark scheme\b/gi, '评分规则')
    .replace(/\s+/g, ' ')
    .replace(/匹配 真题/g, '匹配真题')
    .replace(/本地 真题/g, '本地真题')
}

function normalizeFallbackReason(value: unknown): string | null {
  const raw = normalizeAgentStepText(value)
  if (!raw) return null
  if (/Could not locate question/i.test(raw)) {
    return '未找到这一题对应的评分规则上下文。'
  }
  return raw
}

export function getAgentStepPhaseLabel(step: AgentStepInput): string {
  const title = normalizeAgentStepTitle(step.title)
  if (/上传类型/.test(title)) return '识别上传类型'
  if (/选择批改路径|选择路径/.test(title)) return '选择批改路径'
  if (/匹配/.test(title) || step.grading_route === 'past_paper_mark_scheme') return '匹配真题'
  if (/确认/.test(title) || step.needs_user_confirmation) return '确认题目'
  if (/提取/.test(title)) return '提取答案'
  if (/判分|批改/.test(title)) return '初步判分'
  if (/检查|复核|review/i.test(title)) return '交叉检查'
  if (/反馈|summary|final/i.test(title)) return '生成反馈'

  switch (step.step_type) {
    case 'think':
      return '识别信息'
    case 'act':
      return '处理答案'
    case 'observe':
      return '交叉检查'
    case 'decide':
      return '选择路径'
    case 'final':
      return '生成反馈'
    default:
      return '学习步骤'
  }
}

function confidenceText(prefix: string, value: unknown): string | null {
  const key = cleanText(value)
  if (!key) return null
  return `${prefix} ${CONFIDENCE_LABELS[key] ?? key}`
}

function badge(label: string | null, tone: AgentStepTone): AgentStepBadge | null {
  return label ? { label, tone } : null
}

export function buildAgentStepViewModel(step: AgentStepInput): AgentStepViewModel | null {
  if (step.user_visible === false) return null

  const phaseLabel = getAgentStepPhaseLabel(step)
  const normalizedTitle = normalizeAgentStepTitle(step.title)
  const status = normalizeStatus(step.status)
  const fallbackReason = normalizeFallbackReason(step.mark_scheme_context_error)
  const agentName = cleanText(step.agent_name)
  const tool = cleanText(step.tool)
  const badges = [
    badge(step.grading_route === 'past_paper_mark_scheme' ? '真题匹配' : null, 'success'),
    badge(step.grading_route === 'open_ai_grading' ? '开放批改' : null, fallbackReason ? 'warning' : 'info'),
    badge(confidenceText('匹配', step.match_confidence), step.match_confidence === 'low' ? 'warning' : 'info'),
    badge(confidenceText('评分规则', step.mark_scheme_confidence), step.mark_scheme_confidence === 'low' ? 'warning' : 'success'),
    badge(step.match_source ? MATCH_SOURCE_LABELS[String(step.match_source)] ?? String(step.match_source) : null, 'info'),
    badge(step.paper_id ? `卷子 ${step.paper_id}` : null, 'info'),
    badge(step.question_id ? `题号 ${step.question_id}` : null, 'info'),
    badge(step.needs_user_confirmation ? '需确认' : null, 'warning'),
    badge(fallbackReason ? '已降级' : null, 'warning'),
  ].filter((item): item is AgentStepBadge => item !== null)

  return {
    questionNumber: cleanText(step.question_number) || '本次上传',
    phaseLabel,
    title: normalizedTitle || phaseLabel,
    summary: normalizeAgentStepText(step.summary),
    status,
    agentName: agentName ? AGENT_LABELS[agentName] ?? 'AI 流程' : null,
    tool: tool ? TOOL_LABELS[tool] ?? tool : null,
    badges,
    fallbackReason,
  }
}

export function buildAgentStepViewModels(steps: AgentStepInput[]): AgentStepViewModel[] {
  return steps
    .map(buildAgentStepViewModel)
    .filter((step): step is AgentStepViewModel => step !== null)
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

export function renderAgentStepReplayHtml(steps: AgentStepViewModel[]): string {
  const items = steps.map((step) => {
    const badges = step.badges
      .map((item) => `<span data-tone="${escapeHtml(item.tone)}">${escapeHtml(item.label)}</span>`)
      .join('')
    return [
      '<li>',
      `<strong>${escapeHtml(step.phaseLabel)}</strong>`,
      `<h3>${escapeHtml(step.title)}</h3>`,
      `<p>${escapeHtml(step.summary)}</p>`,
      `<small>${escapeHtml(step.questionNumber)}</small>`,
      step.agentName ? `<small>${escapeHtml(step.agentName)}</small>` : '',
      step.tool ? `<small>${escapeHtml(step.tool)}</small>` : '',
      badges,
      step.fallbackReason ? `<em>已降级：${escapeHtml(step.fallbackReason)}</em>` : '',
      '</li>',
    ].join('')
  })
  return `<main data-testid="agent-step-replay"><ol>${items.join('')}</ol></main>`
}
