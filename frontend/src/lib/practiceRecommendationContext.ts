import type { AgentStepData } from '../api/client'
import type { AnalyzeRequest, PageSummary, QuestionResult, UploadIntent } from '../types'
import type {
  PracticeRecommendationContext,
  PracticeRecommendationRequest,
  PracticeRecommendationSourceQuestion,
  PracticeUploadIntent,
  SubmitAnswerResponse,
} from '../types/practice'

const PRACTICE_INTENT_BY_UPLOAD_INTENT: Record<UploadIntent, PracticeUploadIntent> = {
  past_paper: 'past_paper',
  custom_homework: 'custom_homework',
  unknown: 'unknown',
  full_past_paper_pdf: 'full_past_paper_pdf',
  partial_past_paper_pages: 'partial_past_paper_pages',
  answer_pages_only: 'answer_pages_only',
}

function toPracticeIntent(intent: UploadIntent | undefined): PracticeUploadIntent {
  return intent ? PRACTICE_INTENT_BY_UPLOAD_INTENT[intent] ?? 'unknown' : 'unknown'
}

function parsePaperNumFromPaperCode(value?: string): 1 | 2 | 3 | 4 | 5 | 6 | null {
  const text = (value ?? '').trim()
  const match = text.match(/(?:^|\D)([1-6])[1-3](?:\D|$)/)
  if (!match) return null
  const paper = Number(match[1])
  return paper >= 1 && paper <= 6 ? (paper as 1 | 2 | 3 | 4 | 5 | 6) : null
}

function getResolutionStep(agentSteps: AgentStepData[]): AgentStepData | null {
  return [...agentSteps].reverse().find((step) => {
    return step.question_number === '本次上传' && (step.match_confidence || step.grading_route || step.detail)
  }) ?? null
}

function getPaperNumFromAgentStep(step: AgentStepData | null): 1 | 2 | 3 | 4 | 5 | 6 | null {
  const direct = step?.detail?.catalog_match
  if (direct && typeof direct === 'object' && 'paper_num' in direct) {
    const value = Number((direct as { paper_num?: unknown }).paper_num)
    if (value >= 1 && value <= 6) return value as 1 | 2 | 3 | 4 | 5 | 6
  }
  const paperId = typeof step?.paper_id === 'string' ? step.paper_id : ''
  const match = paperId.match(/_(?:m|s|w)\d{2}_([1-6])[1-3]/i)
  if (!match) return null
  return Number(match[1]) as 1 | 2 | 3 | 4 | 5 | 6
}

export function buildPracticeContext(
  request: AnalyzeRequest | null,
  agentSteps: AgentStepData[],
  confirmedByUser = false,
): PracticeRecommendationContext {
  const step = getResolutionStep(agentSteps)
  const paperNum = getPaperNumFromAgentStep(step) ?? parsePaperNumFromPaperCode(request?.paper_code)
  return {
    upload_intent: toPracticeIntent(request?.upload_intent),
    paper_num: paperNum,
    question_number: request?.question_numbers ?? null,
    match_confidence: step?.match_confidence ?? null,
    confirmed_by_user: confirmedByUser,
    grading_route: step?.grading_route ?? null,
  }
}

export function buildPracticeRequest(args: {
  request: AnalyzeRequest | null
  agentSteps: AgentStepData[]
  summary: PageSummary
  questions: QuestionResult[]
  excludeIds: number[]
  confirmedByUser?: boolean
  preferredDifficultyMin?: number
  preferredDifficultyMax?: number
}): PracticeRecommendationRequest {
  const sourceQuestions: PracticeRecommendationSourceQuestion[] = args.questions.map((q) => ({
    question_number: q.question_number,
    score: q.score,
    full_score: q.full_score,
    is_correct: q.is_correct,
    unanswered: q.unanswered,
    error_type: q.error_type,
    knowledge_tags: q.knowledge_tags ?? [],
    needs_review: q.needs_review,
  }))

  return {
    context: buildPracticeContext(args.request, args.agentSteps, args.confirmedByUser ?? false),
    priority_topics: args.summary.priority_topics ?? [],
    knowledge_tags_summary: args.summary.knowledge_tags_summary ?? {},
    questions: sourceQuestions,
    exclude_ids: args.excludeIds,
    preferred_difficulty_min: args.preferredDifficultyMin,
    preferred_difficulty_max: args.preferredDifficultyMax,
    count: 3,
  }
}

export function difficultyRangeFromPracticeResult(result: SubmitAnswerResponse): [number, number] {
  const full = result.grade_result.full_score || 0
  const score = result.grade_result.score || 0
  const rate = full > 0 ? score / full : 0
  if (result.grade_result.is_correct || rate >= 0.8) return [3, 5]
  if (rate >= 0.4) return [2, 3]
  return [1, 2]
}
