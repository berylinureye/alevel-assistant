import { useCallback, useEffect, useMemo, useState } from 'react'
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

export function PracticeRecommendations({
  request,
  agentSteps,
  summary,
  questions,
  initialResponse,
  loader = recommendPractice,
  answerSubmitter = submitAnswer,
}: Props) {
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

  const baseRequest = useMemo(() => {
    if (!summary) return null
    return buildPracticeRequest({
      request,
      agentSteps,
      summary,
      questions,
      excludeIds: [...recommendedIds, ...completedIds],
      confirmedByUser: confirmed,
    })
  }, [agentSteps, completedIds, confirmed, questions, recommendedIds, request, summary])

  const load = useCallback(async (forceConfirmed = false, preferredRange?: [number, number]) => {
    if (!summary) return
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
      setResponse(next)
      const ids = recommendationQuestionIds(next)
      setRecommendedIds((prev) => Array.from(new Set([...prev, ...ids])))
    } catch (e) {
      setError(e instanceof Error ? e.message : '获取练习推荐失败')
    } finally {
      setLoading(false)
    }
  }, [agentSteps, completedIds, confirmed, loader, questions, recommendedIds, request, summary])

  useEffect(() => {
    if (initialResponse || attemptedInitialLoad || !canLoad || response || loading || !baseRequest) return
    setAttemptedInitialLoad(true)
    void load(false)
  }, [attemptedInitialLoad, baseRequest, canLoad, initialResponse, load, loading, response])

  const handleConfirmAskFirst = useCallback(() => {
    setConfirmed(true)
    void load(true)
  }, [load])

  const handleStart = useCallback((item: PracticeRecommendation) => {
    if (!item.question) return
    setPracticeResult(null)
    setActiveRecommendation(item)
  }, [])

  const handleSubmit = useCallback(async (answer: string, steps: string[]) => {
    const questionId = activeRecommendation?.question_id
    if (!questionId) return
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
    if (!practiceResult) return
    setActiveRecommendation(null)
    const range = difficultyRangeFromPracticeResult(practiceResult)
    void load(true, range)
  }, [load, practiceResult])

  if (!summary || questions.length === 0) return null

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-blue-700">Practice Loop</p>
          <h2 className="mt-1 text-lg font-semibold text-slate-950">
            {response ? modeLabel(response) : '正在判断下一步练习'}
          </h2>
          <p className="mt-1 text-sm leading-6 text-slate-600">
            {response?.message ?? '系统正在根据本次批改结果判断是否适合推荐真实题库练习。'}
          </p>
        </div>
        {response?.match_confidence ? (
          <span className="rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-600">
            识别置信度：{response.match_confidence === 'high' ? '高' : response.match_confidence === 'medium' ? '中' : '低'}
          </span>
        ) : null}
      </div>

      {error ? (
        <p className="mb-4 rounded-md border border-red-100 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
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
              className="rounded-md bg-slate-950 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-800"
            >
              给我 2-3 道类似题
            </button>
            <button
              type="button"
              onClick={() => setResponse({ ...response, recommendation_mode: 'none', message: '已保留本次批改反馈，暂不进入练习。' })}
              className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
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
                    className="mt-3 rounded-md bg-slate-950 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-800"
                  >
                    调整下一题
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
