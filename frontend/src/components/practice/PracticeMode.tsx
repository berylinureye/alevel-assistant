import { useCallback, useState } from 'react'
import { fetchRandomQuestions, submitAnswer } from '../../api/practice'
import type { PracticeConfig, PracticeQuestionState, SubmitAnswerResponse } from '../../types/practice'
import { TopicSelector } from './TopicSelector'
import { DifficultySlider } from './DifficultySlider'
import { PracticeQuestionCard } from './QuestionCard'
import { AnswerInput } from './AnswerInput'
import { PracticeResult } from './PracticeResult'
import { PracticeSummary } from './PracticeSummary'
import { ExportModal } from './ExportModal'
import { PaperBrowser } from './PaperBrowser'

type Phase = 'config' | 'practice' | 'summary'

export function PracticeMode() {
  // Config state
  const [config, setConfig] = useState<PracticeConfig>({
    topics: [],
    difficultyMin: 1,
    difficultyMax: 5,
    count: 5,
  })

  // Session state
  const [phase, setPhase] = useState<Phase>('config')
  const [questionStates, setQuestionStates] = useState<PracticeQuestionState[]>([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showExport, setShowExport] = useState(false)

  const startPractice = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const resp = await fetchRandomQuestions({
        topics: config.topics.length > 0 ? config.topics : undefined,
        difficulty_min: config.difficultyMin,
        difficulty_max: config.difficultyMax,
        count: config.count,
      })
      if (resp.questions.length === 0) {
        setError('题库中没有符合条件的题目，请调整筛选条件或先导入试卷。')
        return
      }
      setQuestionStates(
        resp.questions.map((q) => ({
          question: q,
          studentAnswer: '',
          workingSteps: [],
          submitted: false,
          result: null,
        })),
      )
      setCurrentIndex(0)
      setPhase('practice')
    } catch (e) {
      setError(e instanceof Error ? e.message : '获取题目失败')
    } finally {
      setLoading(false)
    }
  }, [config])

  const handleSubmitAnswer = useCallback(
    async (answer: string, steps: string[]) => {
      const qs = questionStates[currentIndex]
      if (!qs || qs.submitted) return

      setSubmitting(true)
      try {
        const result: SubmitAnswerResponse = await submitAnswer({
          question_id: qs.question.id,
          student_answer: answer,
          working_steps: steps,
        })
        setQuestionStates((prev) => {
          const next = [...prev]
          next[currentIndex] = {
            ...next[currentIndex],
            studentAnswer: answer,
            workingSteps: steps,
            submitted: true,
            result,
          }
          return next
        })
      } catch (e) {
        setError(e instanceof Error ? e.message : '提交失败')
      } finally {
        setSubmitting(false)
      }
    },
    [questionStates, currentIndex],
  )

  const goNext = useCallback(() => {
    if (currentIndex < questionStates.length - 1) {
      setCurrentIndex((i) => i + 1)
    } else {
      setPhase('summary')
    }
  }, [currentIndex, questionStates.length])

  const restart = useCallback(() => {
    setPhase('config')
    setQuestionStates([])
    setCurrentIndex(0)
    setError(null)
  }, [])

  // ------- CONFIG PHASE -------
  if (phase === 'config') {
    return (
      <div className="space-y-6 rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-xl font-bold text-gray-800">练习模式</h2>
        <p className="text-sm text-gray-500">
          从题库中随机抽题，做完后 AI 自动批改并给出反馈。
        </p>

        <TopicSelector
          selected={config.topics}
          onChange={(topics) => setConfig((c) => ({ ...c, topics }))}
        />

        <DifficultySlider
          min={config.difficultyMin}
          max={config.difficultyMax}
          onMinChange={(v) => setConfig((c) => ({ ...c, difficultyMin: v }))}
          onMaxChange={(v) => setConfig((c) => ({ ...c, difficultyMax: v }))}
        />

        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">题目数量</label>
          <select
            value={config.count}
            onChange={(e) => setConfig((c) => ({ ...c, count: Number(e.target.value) }))}
            className="rounded-md border border-gray-300 px-3 py-2 text-sm"
          >
            {[3, 5, 10, 15, 20].map((n) => (
              <option key={n} value={n}>
                {n} 题
              </option>
            ))}
          </select>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <div className="flex gap-3">
          <button
            type="button"
            onClick={startPractice}
            disabled={loading}
            className="flex-1 rounded-md bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? '正在抽题...' : '开始练习'}
          </button>
          <button
            type="button"
            onClick={() => setShowExport(true)}
            className="rounded-md border border-gray-300 bg-white px-4 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            <span className="flex items-center gap-1.5">
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              导出习题
            </span>
          </button>
        </div>

        {showExport && (
          <ExportModal config={config} onClose={() => setShowExport(false)} />
        )}

        {/* 历年真题下载 */}
        <PaperBrowser />
      </div>
    )
  }

  // ------- SUMMARY PHASE -------
  if (phase === 'summary') {
    return <PracticeSummary states={questionStates} onRestart={restart} />
  }

  // ------- PRACTICE PHASE -------
  const currentQ = questionStates[currentIndex]
  if (!currentQ) return null

  return (
    <div className="space-y-4">
      {/* Progress bar */}
      <div className="flex items-center gap-3">
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-gray-100">
          <div
            className="h-full rounded-full bg-blue-500 transition-all"
            style={{ width: `${((currentIndex + (currentQ.submitted ? 1 : 0)) / questionStates.length) * 100}%` }}
          />
        </div>
        <span className="text-xs text-gray-500">
          {currentIndex + 1} / {questionStates.length}
        </span>
      </div>

      <PracticeQuestionCard
        question={currentQ.question}
        index={currentIndex}
        total={questionStates.length}
      >
        {!currentQ.submitted ? (
          <AnswerInput
            onSubmit={handleSubmitAnswer}
            submitting={submitting}
            disabled={false}
          />
        ) : (
          <>
            {currentQ.result && <PracticeResult result={currentQ.result} />}
            <div className="mt-4 flex gap-3">
              <button
                type="button"
                onClick={goNext}
                className="rounded-md bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700"
              >
                {currentIndex < questionStates.length - 1 ? '下一题' : '查看总结'}
              </button>
            </div>
          </>
        )}
      </PracticeQuestionCard>

      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  )
}
