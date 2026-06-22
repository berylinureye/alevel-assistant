import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { AgentStepData } from '../../api/client'
import { recommendPractice } from '../../api/practiceOrchestrator'
import { submitAnswer } from '../../api/practice'
import type { AnalyzeRequest, PageSummary, QuestionResult } from '../../types'
import type {
  PracticeRecommendation,
  PracticeRecommendationResponse,
  SubmitAnswerResponse,
} from '../../types/practice'
import {
  buildPracticeRequest,
  difficultyRangeFromPracticeResult,
} from '../../lib/practiceRecommendationContext'
import { AnswerInput } from './AnswerInput'
import { PracticeQuestionCard } from './QuestionCard'
import { PracticeResult } from './PracticeResult'

interface Props {
  request: AnalyzeRequest | null
  agentSteps: AgentStepData[]
  summary: PageSummary | null
  questions: QuestionResult[]
  initialResponse?: PracticeRecommendationResponse
  loader?: typeof recommendPractice
  answerSubmitter?: typeof submitAnswer
}

interface LoadArgs {
  forceConfirmed: boolean
  preferredRange?: [number, number]
}

function stableKey(parts: Array<boolean | number | string | null | undefined>): string {
  return parts.map((part) => (part == null ? '' : String(part))).join('~')
}

function recordKey(value: Record<string, number> | undefined): string {
  return Object.entries(value ?? {})
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, count]) => `${key}:${count}`)
    .join(',')
}

function modeLabel(response: PracticeRecommendationResponse): string {
  if (response.recommendation_mode === 'auto') return '下一步练习'
  if (response.recommendation_mode === 'ask_first') return '要不要继续练这个点？'
  return '练习推荐暂不可用'
}

function nextActionText(result: SubmitAnswerResponse): string {
  const full = result.grade_result.full_score || 0
  const rate = full > 0 ? result.grade_result.score / full : 0
  if (result.grade_result.is_correct || rate >= 0.8) return '这题掌握不错，可以升一点难度。'
  if (rate >= 0.4) return '你已经拿到部分分数，建议继续做一道同主题中等难度题。'
  return '先回看讲解，再做一道更基础的同主题题。'
}

function recommendationQuestionIds(response: PracticeRecommendationResponse | undefined): number[] {
  return response?.recommendations
    .map((item) => item.question_id)
    .filter((id): id is number => typeof id === 'number') ?? []
}

function recommendationResponseKey(response: PracticeRecommendationResponse | undefined): string {
  if (!response) return ''
  return stableKey([
    response.status,
    response.recommendation_mode,
    response.message,
    response.detected_topic,
    response.detected_subtopic,
    response.paper_num,
    response.match_confidence,
    response.recommendations
      .map((item) => stableKey([
        item.id,
        item.question_id,
        item.topic,
        item.subtopic,
        item.difficulty,
        item.title,
        item.reason,
        item.source_label,
      ]))
      .join('|'),
  ])
}

function gradingRunKey(
  request: AnalyzeRequest | null,
  summary: PageSummary | null,
  questions: QuestionResult[],
): string {
  const requestKey = stableKey([
    request?.upload_intent,
    request?.paper_code,
    request?.question_numbers,
    request?.upload_ids?.map((id) => id ?? '').join(','),
    request?.images.map((file) => stableKey([file.name, file.size, file.lastModified, file.type])).join(','),
  ])

  const summaryKey = summary
    ? stableKey([
        summary.total_questions,
        summary.correct_count,
        summary.incorrect_count,
        summary.unanswered_count,
        summary.review_count,
        summary.score_total,
        summary.full_score_total,
        recordKey(summary.knowledge_tags_summary),
        summary.priority_topics
          .map((topic) => stableKey([topic.topic, topic.subtopic, topic.chapter, topic.error_count]))
          .join('|'),
      ])
    : ''

  const questionsKey = questions
    .map((question) => stableKey([
      question.question_number,
      question.page,
      question.score,
      question.full_score,
      question.is_correct,
      question.unanswered,
      question.needs_review,
      question.error_type,
      question.knowledge_tags?.join(','),
      question.grading_route,
      question.mark_scheme_confidence,
      question.student_answer,
      question.correct_answer,
    ]))
    .join('|')

  return stableKey([requestKey, summaryKey, questionsKey])
}

export function PracticeRecommendations({
  request,
  agentSteps,
  summary,
  questions,
  initialResponse,
  loader = recommendPractice,
  answerSubmitter = submitAnswer,
}: Props) {
  const runKey = useMemo(() => gradingRunKey(request, summary, questions), [questions, request, summary])
  const initialResponseKey = useMemo(() => recommendationResponseKey(initialResponse), [initialResponse])
  const initialResponseRef = useRef(initialResponse)
  const initialRecommendedIdsRef = useRef(recommendationQuestionIds(initialResponse))
  const requestIdRef = useRef(0)
  const loadingRef = useRef(false)
  const lastLoadArgsRef = useRef<LoadArgs>({ forceConfirmed: false })

  const [response, setResponse] = useState<PracticeRecommendationResponse | null>(initialResponse ?? null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [confirmed, setConfirmed] = useState(false)
  const [activeRecommendation, setActiveRecommendation] = useState<PracticeRecommendation | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [practiceResult, setPracticeResult] = useState<SubmitAnswerResponse | null>(null)
  const [attemptedInitialLoad, setAttemptedInitialLoad] = useState(false)
  const [recommendedIds, setRecommendedIds] = useState<number[]>(() => recommendationQuestionIds(initialResponse))
  const [completedIds, setCompletedIds] = useState<number[]>([])

  const canLoad = summary !== null && questions.length > 0

  useEffect(() => {
    initialResponseRef.current = initialResponse
    initialRecommendedIdsRef.current = recommendationQuestionIds(initialResponse)
  }, [initialResponse])

  useEffect(() => {
    requestIdRef.current += 1
    loadingRef.current = false
    lastLoadArgsRef.current = { forceConfirmed: false }
    setResponse(initialResponseRef.current ?? null)
    setLoading(false)
    setError(null)
    setConfirmed(false)
    setActiveRecommendation(null)
    setSubmitting(false)
    setPracticeResult(null)
    setAttemptedInitialLoad(false)
    setRecommendedIds(initialRecommendedIdsRef.current)
    setCompletedIds([])
  }, [initialResponseKey, runKey])

  const load = useCallback(async (forceConfirmed = false, preferredRange?: [number, number]): Promise<boolean> => {
    if (!summary || loadingRef.current) return false
    const requestId = requestIdRef.current + 1
    requestIdRef.current = requestId
    loadingRef.current = true
    lastLoadArgsRef.current = { forceConfirmed, preferredRange }
    setLoading(true)
    setError(null)
    try {
      const body = buildPracticeRequest({
        request,
        agentSteps,
        summary,
        questions,
        excludeIds: [...recommendedIds, ...completedIds],
        confirmedByUser: forceConfirmed || confirmed,
        preferredDifficultyMin: preferredRange?.[0],
        preferredDifficultyMax: preferredRange?.[1],
      })
      const next = await loader(body)
      if (requestIdRef.current !== requestId) return false
      setResponse(next)
      const ids = recommendationQuestionIds(next)
      setRecommendedIds((prev) => Array.from(new Set([...prev, ...ids])))
      return true
    } catch (e) {
      if (requestIdRef.current !== requestId) return false
      setError(e instanceof Error ? e.message : '获取练习推荐失败')
      return false
    } finally {
      if (requestIdRef.current === requestId) {
        loadingRef.current = false
        setLoading(false)
      }
    }
  }, [agentSteps, completedIds, confirmed, loader, questions, recommendedIds, request, summary])

  useEffect(() => {
    if (initialResponse || attemptedInitialLoad || !canLoad || response || loading) return
    setAttemptedInitialLoad(true)
    void load(false)
  }, [attemptedInitialLoad, canLoad, initialResponse, load, loading, response])

  const handleRetry = useCallback(() => {
    const { forceConfirmed, preferredRange } = lastLoadArgsRef.current
    void load(forceConfirmed, preferredRange)
  }, [load])

  const handleConfirmAskFirst = useCallback(() => {
    if (loading) return
    setConfirmed(true)
    void load(true)
  }, [load, loading])

  const handleStart = useCallback((item: PracticeRecommendation) => {
    if (!item.question) return
    setPracticeResult(null)
    setActiveRecommendation(item)
  }, [])

  const handleSubmit = useCallback(async (answer: string, steps: string[]) => {
    const questionId = activeRecommendation?.question_id
    if (questionId == null) return
    setSubmitting(true)
    setError(null)
    try {
      const result = await answerSubmitter({
        question_id: questionId,
        student_answer: answer,
        working_steps: steps,
      })
      setPracticeResult(result)
      setCompletedIds((prev) => Array.from(new Set([...prev, questionId])))
    } catch (e) {
      setError(e instanceof Error ? e.message : '提交练习答案失败')
    } finally {
      setSubmitting(false)
    }
  }, [activeRecommendation, answerSubmitter])

  const handleNextAdaptive = useCallback(() => {
    if (!practiceResult || loading) return
    const range = difficultyRangeFromPracticeResult(practiceResult)
    void load(true, range).then((loaded) => {
      if (!loaded) return
      setActiveRecommendation(null)
      setPracticeResult(null)
    })
  }, [load, loading, practiceResult])

  if (!summary || questions.length === 0) return null

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-blue-700">Practice Loop</p>
          <h2 className="mt-1 text-lg font-semibold text-slate-950">
            {response ? modeLabel(response) : error ? '练习推荐加载失败' : '正在判断下一步练习'}
          </h2>
          <p className="mt-1 text-sm leading-6 text-slate-600">
            {response?.message ?? (error ? '推荐暂时没有加载成功，可以点击重试重新匹配题库。' : '系统正在根据本次批改结果判断是否适合推荐真实题库练习。')}
          </p>
        </div>
        {response?.match_confidence ? (
          <span className="rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-600">
            识别置信度：{response.match_confidence === 'high' ? '高' : response.match_confidence === 'medium' ? '中' : '低'}
          </span>
        ) : null}
      </div>

      {error ? (
        <div
          role="alert"
          className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-md border border-red-100 bg-red-50 px-3 py-2 text-sm text-red-700"
        >
          <p>{error}</p>
          <button
            type="button"
            onClick={handleRetry}
            disabled={loading || !canLoad}
            className="rounded-md border border-red-200 bg-white px-3 py-1.5 text-xs font-semibold text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? '正在重试...' : '重新获取推荐'}
          </button>
        </div>
      ) : null}

      {loading ? (
        <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-4 text-sm text-slate-500">
          正在从题库匹配练习题...
        </div>
      ) : null}

      {response?.recommendation_mode === 'ask_first' ? (
        <div className="rounded-md border border-blue-100 bg-blue-50/70 p-4">
          <p className="text-sm font-medium text-slate-950">
            检测到：{response.paper_num ? `P${response.paper_num} · ` : ''}{response.detected_topic ?? '相似题型'}
          </p>
          <p className="mt-1 text-sm leading-6 text-slate-600">{response.message}</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={handleConfirmAskFirst}
              disabled={loading}
              className="rounded-md bg-slate-950 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              给我 2-3 道类似题
            </button>
            <button
              type="button"
              onClick={() => setResponse({ ...response, recommendation_mode: 'none', message: '已保留本次批改反馈，暂不进入练习。' })}
              disabled={loading}
              className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              暂时不用
            </button>
          </div>
        </div>
      ) : null}

      {response?.recommendation_mode === 'none' ? (
        <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-4 text-sm leading-6 text-slate-600">
          {response.message}
        </div>
      ) : null}

      {response?.recommendations.length ? (
        <div className="grid gap-3 md:grid-cols-3">
          {response.recommendations.map((item) => (
            <article key={item.id} className="rounded-md border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold text-slate-950">{item.title}</p>
                  <p className="mt-1 text-xs text-slate-500">{item.source_label}</p>
                </div>
                <span className="rounded-md bg-white px-2 py-1 text-xs font-medium text-slate-600 ring-1 ring-slate-200">
                  {item.difficulty}
                </span>
              </div>
              <p className="mt-3 text-sm leading-6 text-slate-600">{item.reason}</p>
              <button
                type="button"
                onClick={() => handleStart(item)}
                disabled={!item.question}
                className="mt-4 w-full rounded-md bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                开始练习
              </button>
            </article>
          ))}
        </div>
      ) : null}

      {activeRecommendation?.question ? (
        <div className="mt-5 border-t border-slate-100 pt-5">
          <PracticeQuestionCard question={activeRecommendation.question} index={0} total={1}>
            {!practiceResult ? (
              <AnswerInput onSubmit={handleSubmit} submitting={submitting} disabled={false} />
            ) : (
              <>
                <PracticeResult result={practiceResult} />
                <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3">
                  <p className="text-sm text-slate-700">{nextActionText(practiceResult)}</p>
                  <button
                    type="button"
                    onClick={handleNextAdaptive}
                    disabled={loading}
                    className="mt-3 rounded-md bg-slate-950 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {loading ? '正在调整...' : '调整下一题'}
                  </button>
                </div>
              </>
            )}
          </PracticeQuestionCard>
        </div>
      ) : null}
    </section>
  )
}
