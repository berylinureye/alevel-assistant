import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { consumePendingUpload } from './pages/landing/lib/pendingUpload'
import { analyzeHomeworkStreaming, isAbortError, mergePageSummaries } from './api/client'
import type { AgentStepData, QuestionExtractedData } from './api/client'
import type { AnalyzeRequest, PageSummary as PageSummaryType, QuestionResult } from './types'
import { UploadForm } from './components/UploadForm'
import { PageSummary } from './components/PageSummary'
import { QuestionCard } from './components/QuestionCard'
import { SkeletonQuestionCard, type AgentRunState } from './components/SkeletonQuestionCard'
import { FilterBar, type QuestionFilter } from './components/FilterBar'
import { StatusMessage } from './components/StatusMessage'
import { HistoryTab } from './components/HistoryTab'
import { SummaryTab } from './components/SummaryTab'
import { ProfileTab } from './components/ProfileTab'
import { PaperBrowser } from './components/practice/PaperBrowser'
import { PracticeRecommendations } from './components/practice/PracticeRecommendations'
import { FeedbackPanel } from './components/FeedbackPanel'
import { saveRecord } from './lib/history'
import { newSessionId } from './lib/userId'
import { getAgentDisplay } from './utils/modelDisplay'
import './index.css'

type AppTab = 'grading' | 'practice' | 'history' | 'summary' | 'profile'

const TAB_LABELS: Array<{ key: AppTab; label: string }> = [
  { key: 'grading', label: '作业批改' },
  { key: 'history', label: '历史记录' },
  { key: 'summary', label: '总结' },
  { key: 'practice', label: '刷题' },
]

function getImageUrlForQuestion(questionNumber: string, imageUrls: string[]): string | undefined {
  if (imageUrls.length === 0) return undefined
  if (imageUrls.length === 1) return imageUrls[0]
  const match = questionNumber.match(/^图片\s*(\d+)/)
  if (match) {
    const idx = parseInt(match[1], 10) - 1
    if (idx >= 0 && idx < imageUrls.length) return imageUrls[idx]
  }
  return imageUrls[0]
}

function WorkflowPreview() {
  const steps = [
    { label: '识别卷子', text: '先判断是否来自 Past Paper，能匹配就读取本地题库上下文' },
    { label: '对照规则', text: '优先按 mark scheme 路由；信息不足时回退开放批改' },
    { label: '学习诊断', text: '输出每题得分、错因、复习重点和下一步练习' },
  ]

  return (
    <aside className="space-y-4 rounded-lg border border-slate-200 bg-white/85 p-5 shadow-sm">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-blue-700">Learning Workflow</p>
        <h2 className="mt-2 text-lg font-semibold text-slate-950">不是黑盒批改，而是先找依据</h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          上传后你会看到系统如何识别上传内容、选择批改路径，并把结果转成可执行的学习建议。
        </p>
      </div>

      <ol className="space-y-3">
        {steps.map((step, idx) => (
          <li key={step.label} className="grid grid-cols-[2rem_minmax(0,1fr)] gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-md bg-blue-50 text-xs font-semibold text-blue-700 ring-1 ring-blue-100">
              {idx + 1}
            </div>
            <div className="min-w-0 border-b border-slate-100 pb-3 last:border-b-0 last:pb-0">
              <p className="text-sm font-semibold text-slate-950">{step.label}</p>
              <p className="mt-0.5 text-xs leading-5 text-slate-500">{step.text}</p>
            </div>
          </li>
        ))}
      </ol>

      <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
        <div className="flex items-center justify-between gap-3">
          <span className="text-xs font-medium text-slate-600">适合</span>
          <span className="text-xs text-slate-500">CAIE Maths 9709</span>
        </div>
        <div className="mt-3 grid grid-cols-3 gap-2 text-center">
          {['图片', 'PDF', '真题卷'].map((item) => (
            <span key={item} className="rounded-md bg-white px-2 py-2 text-xs font-medium text-slate-600 ring-1 ring-slate-200">
              {item}
            </span>
          ))}
        </div>
      </div>
    </aside>
  )
}

export default function App() {
  const [activeTab, setActiveTab] = useState<AppTab>('grading')
  const [pendingUploadFiles, setPendingUploadFiles] = useState<File[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [analysisProgress, setAnalysisProgress] = useState<{ current: number; total: number } | null>(
    null,
  )
  const [thinkingLog, setThinkingLog] = useState<string[]>([])
  const [agentSteps, setAgentSteps] = useState<AgentStepData[]>([])
  const [progressDetail, setProgressDetail] = useState<string | null>(null)

  const [questions, setQuestions] = useState<QuestionResult[]>([])
  const [extractedQuestions, setExtractedQuestions] = useState<QuestionExtractedData[]>([])
  const [agentStatusByQuestion, setAgentStatusByQuestion] = useState<
    Record<string, Record<string, AgentRunState>>
  >({})
  const [summary, setSummary] = useState<PageSummaryType | null>(null)
  const [lastAnalyzeRequest, setLastAnalyzeRequest] = useState<AnalyzeRequest | null>(null)
  const [totalExpected, setTotalExpected] = useState(0)
  /** 与 totalExpected 同步，供回调中立即读取（多图并发） */
  const totalExpectedRef = useRef(0)

  const [sessionId, setSessionId] = useState<string | null>(null)
  const [questionFilter, setQuestionFilter] = useState<QuestionFilter>('all')
  const [expandedByQuestionId, setExpandedByQuestionId] = useState<Record<string, boolean>>({})
  const [imageUrls, setImageUrls] = useState<string[]>([])
  const [infoMessage, setInfoMessage] = useState<string | null>(null)
  const [dismissPanelVersion, setDismissPanelVersion] = useState(0)
  const imageUrlsRef = useRef<string[]>([])
  const analysisAbortControllerRef = useRef<AbortController | null>(null)

  useEffect(() => {
    return () => {
      analysisAbortControllerRef.current?.abort()
      imageUrlsRef.current.forEach((url) => URL.revokeObjectURL(url))
    }
  }, [])

  // Pick up files passed through from the landing page CTA.
  useEffect(() => {
    const files = consumePendingUpload()
    if (files.length > 0) {
      queueMicrotask(() => {
        setPendingUploadFiles(files)
        setActiveTab('grading')
      })
    }
  }, [])

  const handleResetUpload = useCallback(() => {
    analysisAbortControllerRef.current?.abort()
    analysisAbortControllerRef.current = null
    imageUrlsRef.current.forEach((url) => URL.revokeObjectURL(url))
    imageUrlsRef.current = []
    setImageUrls([])
    totalExpectedRef.current = 0
    setTotalExpected(0)
    setLoading(false)
    setError(null)
    setInfoMessage(null)
    setQuestions([])
    setExtractedQuestions([])
    setAgentStatusByQuestion({})
    setSummary(null)
    setLastAnalyzeRequest(null)
    setThinkingLog([])
    setAgentSteps([])
    setProgressDetail(null)
    setAnalysisProgress(null)
    setQuestionFilter('all')
    setExpandedByQuestionId({})
    setDismissPanelVersion((v) => v + 1)
  }, [])

  const handleCancelAnalysis = useCallback(() => {
    if (!loading) return
    analysisAbortControllerRef.current?.abort()
    analysisAbortControllerRef.current = null
    setLoading(false)
    setError(null)
    setInfoMessage('已取消本次批改，可调整图片后重新开始')
    setAnalysisProgress(null)
    setProgressDetail(null)
    setThinkingLog((prev) => [...prev, '已取消本次批改'])
    setAgentSteps((prev) => [
      ...prev,
      {
        question_number: '本次批改',
        step_type: 'final',
        title: '已取消',
        summary: '用户取消了本次批改，可调整图片后重新开始。',
        status: 'completed',
      },
    ])
    setDismissPanelVersion((v) => v + 1)
  }, [loading])

  const handleSubmit = async (req: AnalyzeRequest) => {
    analysisAbortControllerRef.current?.abort()
    const abortController = new AbortController()
    analysisAbortControllerRef.current = abortController
    imageUrlsRef.current.forEach((url) => URL.revokeObjectURL(url))
    const newUrls = req.images.map((file) => URL.createObjectURL(file))
    setLastAnalyzeRequest(req)
    imageUrlsRef.current = newUrls
    setImageUrls(newUrls)

    totalExpectedRef.current = 0
    setTotalExpected(0)
    setLoading(true)
    setError(null)
    setInfoMessage(null)
    setQuestions([])
    setExtractedQuestions([])
    setAgentStatusByQuestion({})
    setSummary(null)
    setThinkingLog([])
    setAgentSteps([])
    setProgressDetail(null)
    setAnalysisProgress(null)
    setQuestionFilter('all')
    setExpandedByQuestionId({})
    setSessionId(newSessionId())

    const collectedQuestions: QuestionResult[] = []
    let collectedSummary: PageSummaryType | null = null

    try {
      await analyzeHomeworkStreaming(req, {
        onSegmentation: (data) => {
          totalExpectedRef.current += data.question_count
          setTotalExpected(totalExpectedRef.current)
          setThinkingLog((prev) => [
            ...prev,
            `识别到 ${data.question_count} 道题目，开始逐题批改…`,
          ])
        },
        onQuestion: (q) => {
          collectedQuestions.push(q)
          setQuestions((prev) => {
            const next = [...prev, q]
            const exp = Math.max(totalExpectedRef.current, next.length)
            setProgressDetail(`已完成 ${next.length}/${exp} 道题…`)
            return next
          })
        },
        onSummary: (s) => {
          collectedSummary = collectedSummary ? mergePageSummaries([collectedSummary, s]) : s
          setSummary((prev) => (prev ? mergePageSummaries([prev, s]) : s))
        },
        onError: (msg) => {
          setError(msg)
        },
        onDone: () => {
          setLoading(false)
          setAnalysisProgress(null)
        },
        onImageStart: (current, total) => {
          setAnalysisProgress({ current, total })
        },
        onSolution: (data) => {
          const { question_number, solution_text } = data
          if (question_number && solution_text) {
            const idx = collectedQuestions.findIndex((q) => q.question_number === question_number)
            if (idx >= 0) collectedQuestions[idx] = { ...collectedQuestions[idx], solution_text }
            setQuestions((prev) =>
              prev.map((q) =>
                q.question_number === question_number
                  ? { ...q, solution_text }
                  : q,
              ),
            )
          }
        },
        onQuestionExtracted: (data) => {
          setExtractedQuestions((prev) => {
            if (prev.some((e) => e.question_number === data.question_number)) return prev
            return [...prev, data]
          })
        },
        onAgentProgress: (data) => {
          const { question_number, agent_name, status } = data
          const modelId = (data as { model_id?: string }).model_id
          if (agent_name && status && question_number) {
            setAgentStatusByQuestion((prev) => {
              const existing = prev[question_number] ?? {}
              return {
                ...prev,
                [question_number]: {
                  ...existing,
                  [agent_name]: { agent_name, status, model_id: modelId },
                },
              }
            })
          }
          if (agent_name && status) {
            const statusMap: Record<string, string> = {
              started: '开始批改',
              completed: '批改完成',
              timeout: '超时',
              failed: '失败',
              voting: '投票中',
            }
            const label = statusMap[status] ?? status
            const agentDisplay = getAgentDisplay(agent_name)
            setThinkingLog((prev) => [
              ...prev,
              `第 ${question_number} 题 · ${agentDisplay.shortName} · ${agentDisplay.roleName} · ${label}`,
            ])
          }
        },
        onAgentStep: (data) => {
          setAgentSteps((prev) => [...prev.slice(-119), data])
        },
      }, {
        signal: abortController.signal,
      })
      analysisAbortControllerRef.current = null
      if (collectedQuestions.length > 0) {
        try {
          saveRecord({ questions: collectedQuestions, summary: collectedSummary })
        } catch (e) {
          console.warn('保存历史记录失败:', e)
        }
      }
    } catch (err) {
      analysisAbortControllerRef.current = null
      if (isAbortError(err)) {
        return
      }
      const message = err instanceof Error ? err.message : String(err)
      setError(message)
      setLoading(false)
      setAnalysisProgress(null)
    }
  }

  const sortedQuestions = useMemo(() => {
    return [...questions].sort((a, b) => {
      const parseKey = (qn: string) => {
        const m = qn.match(/^图片\s*(\d+)\s*-\s*(.+)$/)
        if (m) return { img: parseInt(m[1], 10), q: m[2] }
        return { img: 0, q: qn }
      }
      const ka = parseKey(a.question_number)
      const kb = parseKey(b.question_number)
      if (ka.img !== kb.img) return ka.img - kb.img
      return ka.q.localeCompare(kb.q, undefined, { numeric: true })
    })
  }, [questions])

  /** 已批改题号集合，用于判断是否渲染骨架卡 */
  const gradedQuestionNumbers = useMemo(
    () => new Set(questions.map((q) => q.question_number)),
    [questions],
  )

  /** 仅保留尚未批改的 extracted（骨架卡），按与 sortedQuestions 相同规则排序 */
  const pendingSkeletons = useMemo(() => {
    const parseKey = (qn: string) => {
      const m = qn.match(/^图片\s*(\d+)\s*-\s*(.+)$/)
      if (m) return { img: parseInt(m[1], 10), q: m[2] }
      return { img: 0, q: qn }
    }
    return extractedQuestions
      .filter((e) => !gradedQuestionNumbers.has(e.question_number))
      .sort((a, b) => {
        const ka = parseKey(a.question_number)
        const kb = parseKey(b.question_number)
        if (ka.img !== kb.img) return ka.img - kb.img
        return ka.q.localeCompare(kb.q, undefined, { numeric: true })
      })
  }, [extractedQuestions, gradedQuestionNumbers])

  const filterCounts = useMemo(() => {
    const qs = sortedQuestions
    return {
      all: qs.length,
      correct: qs.filter((q) => q.is_correct).length,
      wrong: qs.filter((q) => !q.is_correct && !q.unanswered && q.error_type !== 'pending_review').length,
      unanswered: qs.filter((q) => q.unanswered).length,
    }
  }, [sortedQuestions])

  const filteredQuestions = useMemo(() => {
    return sortedQuestions.filter((q) => {
      if (questionFilter === 'all') return true
      if (questionFilter === 'correct') return q.is_correct
      if (questionFilter === 'unanswered') return q.unanswered
      return !q.is_correct && !q.unanswered && q.error_type !== 'pending_review'
    })
  }, [sortedQuestions, questionFilter])

  const allVisibleExpanded = useMemo(() => {
    if (filteredQuestions.length === 0) return false
    return filteredQuestions.every((q) => expandedByQuestionId[q.question_number])
  }, [filteredQuestions, expandedByQuestionId])

  const handleToggleExpandAll = useCallback(() => {
    setExpandedByQuestionId((prev) => {
      if (filteredQuestions.length === 0) return prev
      const expand = !filteredQuestions.every((q) => prev[q.question_number])
      const next = { ...prev }
      for (const q of filteredQuestions) {
        next[q.question_number] = expand
      }
      return next
    })
  }, [filteredQuestions])

  const toggleQuestionExpand = useCallback((questionNumber: string) => {
    setExpandedByQuestionId((prev) => ({
      ...prev,
      [questionNumber]: !prev[questionNumber],
    }))
  }, [])

  const showSummaryBlock = summary !== null

  return (
    <div className="min-h-screen overflow-x-hidden bg-[radial-gradient(circle_at_top_left,#eff6ff_0,#f8fafc_34%,#f6f7f9_100%)] px-4 py-5 text-slate-950 sm:px-6 lg:px-8">
      <div className="mx-auto flex w-full min-w-0 max-w-7xl flex-col gap-5">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-slate-950">A-Level Assistant</p>
            <p className="mt-0.5 text-xs text-slate-500">AI 作业批改与学习诊断</p>
          </div>
          <button
            type="button"
            onClick={() => setActiveTab('profile')}
            className={`inline-flex h-9 shrink-0 items-center justify-center gap-2 rounded-md border px-3 text-sm font-medium transition ${
              activeTab === 'profile'
                ? 'border-blue-500 bg-blue-50 text-blue-700'
                : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
            }`}
            aria-label="个人"
          >
            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
              <circle cx="12" cy="8" r="4" />
              <path d="M4 21c0-4.4 3.6-8 8-8s8 3.6 8 8" strokeLinecap="round" />
            </svg>
            个人
          </button>
        </div>

        <header className="px-1 py-1">
          <h1 className="text-xl font-semibold tracking-tight text-slate-950 sm:text-2xl">
            作业批改
          </h1>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-600 [overflow-wrap:anywhere]">
            上传整页作业图片，系统会识别题目、批改答案，并生成逐题反馈和复习重点。
          </p>
        </header>

        <nav className="flex min-w-0 gap-1 overflow-x-auto rounded-lg border border-slate-200 bg-white/80 p-1 shadow-sm backdrop-blur">
          {TAB_LABELS.map((t) => (
            <button
              key={t.key}
              type="button"
              onClick={() => setActiveTab(t.key)}
              className={`whitespace-nowrap rounded-md px-4 py-2 text-sm font-medium transition ${
                activeTab === t.key
                  ? 'bg-slate-950 text-white shadow-sm'
                  : 'text-slate-500 hover:bg-slate-100 hover:text-slate-800'
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>

        {activeTab === 'practice' ? (
          <div key="practice" className="view-fade-in space-y-4 rounded-lg border border-slate-200 bg-white/85 p-5 shadow-sm">
            <div>
              <h2 className="text-lg font-semibold text-slate-950">历年真题</h2>
              <p className="mt-1 text-sm text-slate-600">
                按 Paper、年份、级别筛选 Cambridge 9709 真题，一键下载 QP / MS PDF。
              </p>
            </div>
            <PaperBrowser defaultOpen />
          </div>
        ) : activeTab === 'history' ? (
          <div key="history" className="view-fade-in">
            <HistoryTab />
          </div>
        ) : activeTab === 'summary' ? (
          <div key="summary" className="view-fade-in">
            <SummaryTab />
          </div>
        ) : activeTab === 'profile' ? (
          <div key="profile" className="view-fade-in">
            <ProfileTab />
          </div>
        ) : (
          <>
        {!(loading || questions.length > 0 || error) ? (
          <div className="view-fade-in grid min-w-0 gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
            <div className="min-w-0">
              <UploadForm
                onSubmit={handleSubmit}
                loading={loading}
                onResetUpload={handleResetUpload}
                onCancelAnalysis={handleCancelAnalysis}
                initialFiles={pendingUploadFiles}
                onInitialFilesConsumed={() => setPendingUploadFiles(null)}
              />
            </div>
            <WorkflowPreview />
          </div>
        ) : (
          <div className="view-fade-in space-y-6">
            <div className="flex items-center justify-between gap-3">
              {loading ? (
                <button
                  type="button"
                  onClick={() => {
                    handleCancelAnalysis()
                    handleResetUpload()
                  }}
                  className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  <span aria-hidden>←</span> 返回重新上传并取消本次批改
                </button>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={handleResetUpload}
                    className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50"
                  >
                    <span aria-hidden>←</span> 返回
                  </button>
                  <div className="flex items-center gap-2">
                    <span className="hidden text-xs text-slate-500 sm:inline">已保存至历史记录</span>
                    <button
                      type="button"
                      onClick={handleResetUpload}
                      className="inline-flex items-center gap-1.5 rounded-md bg-slate-950 px-3 py-1.5 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800"
                    >
                      开始下一轮拍摄 <span aria-hidden>→</span>
                    </button>
                  </div>
                </>
              )}
            </div>

            <StatusMessage
              loading={loading}
              error={error}
              infoMessage={infoMessage}
              analysisProgress={analysisProgress}
              thinkingLog={thinkingLog}
              agentSteps={agentSteps}
              progressDetail={progressDetail}
              totalExpected={totalExpected}
              dismissPanelVersion={dismissPanelVersion}
              gradingDone={totalExpected > 0 && questions.length >= totalExpected}
            />

            {questions.length > 0 || pendingSkeletons.length > 0 ? (
              <>
                {questions.length > 0 ? (
                  <FilterBar
                    filter={questionFilter}
                    onFilterChange={setQuestionFilter}
                    counts={filterCounts}
                    onToggleExpandAll={handleToggleExpandAll}
                    allVisibleExpanded={allVisibleExpanded}
                    hasVisibleQuestions={filteredQuestions.length > 0}
                  />
                ) : null}

                <div className="space-y-4">
                  {filteredQuestions.length === 0 && questions.length > 0 && questionFilter !== 'all' ? (
                    <p className="rounded-lg border border-slate-200 bg-white/80 px-4 py-6 text-sm text-slate-500">
                      没有符合当前筛选的题目。
                    </p>
                  ) : (
                    filteredQuestions.map((q) => (
                      <QuestionCard
                        key={q.question_number}
                        question={q}
                        expanded={Boolean(expandedByQuestionId[q.question_number])}
                        onToggleExpand={() => toggleQuestionExpand(q.question_number)}
                        imageUrl={getImageUrlForQuestion(q.question_number, imageUrls)}
                      />
                    ))
                  )}
                  {questionFilter === 'all'
                    ? pendingSkeletons.map((e) => (
                        <SkeletonQuestionCard
                          key={`skeleton-${e.question_number}`}
                          data={e}
                          agents={agentStatusByQuestion[e.question_number] ?? {}}
                          imageUrl={getImageUrlForQuestion(e.question_number, imageUrls)}
                        />
                      ))
                    : null}
                </div>
              </>
            ) : null}

            {showSummaryBlock ? (
              <>
                <PageSummary summary={summary} />
                <PracticeRecommendations
                  request={lastAnalyzeRequest}
                  agentSteps={agentSteps}
                  summary={summary}
                  questions={questions}
                />
              </>
            ) : null}

            {!loading && questions.length > 0 ? (
              <FeedbackPanel
                sessionId={sessionId}
                context={{
                  total_questions: questions.length,
                  correct_count: questions.filter((q) => q.is_correct).length,
                  incorrect_count: questions.filter((q) => !q.is_correct && !q.unanswered && q.error_type !== 'pending_review').length,
                  unanswered_count: questions.filter((q) => q.unanswered).length,
                }}
              />
            ) : null}
          </div>
        )}
          </>
        )}
      </div>
    </div>
  )
}
