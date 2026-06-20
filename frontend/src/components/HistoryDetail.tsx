import { useCallback, useMemo, useState } from 'react'
import type { HistoryRecord } from '../lib/history'
import { PageSummary } from './PageSummary'
import { QuestionCard } from './QuestionCard'
import { FilterBar, type QuestionFilter } from './FilterBar'

function formatDateTime(ts: number): string {
  const d = new Date(ts)
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function parseKey(qn: string): { img: number; q: string } {
  const m = qn.match(/^图片\s*(\d+)\s*-\s*(.+)$/)
  if (m) return { img: parseInt(m[1], 10), q: m[2] }
  return { img: 0, q: qn }
}

export interface HistoryDetailProps {
  record: HistoryRecord
  onBack: () => void
}

export function HistoryDetail({ record, onBack }: HistoryDetailProps) {
  const [questionFilter, setQuestionFilter] = useState<QuestionFilter>('all')
  const [expandedByQuestionId, setExpandedByQuestionId] = useState<Record<string, boolean>>({})

  const sortedQuestions = useMemo(() => {
    return [...record.questions].sort((a, b) => {
      const ka = parseKey(a.question_number)
      const kb = parseKey(b.question_number)
      if (ka.img !== kb.img) return ka.img - kb.img
      return ka.q.localeCompare(kb.q, undefined, { numeric: true })
    })
  }, [record.questions])

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

  const answered = record.questions.filter((q) => !q.unanswered)
  const correct = answered.filter((q) => q.is_correct).length
  const pendingReview = record.questions.filter(
    (q) => !q.unanswered && q.error_type === 'pending_review',
  ).length
  const wrong = answered.length - correct - pendingReview
  const total = record.questions.length
  const graded = answered.length - pendingReview
  const accuracy = graded > 0 ? Math.round((correct / graded) * 100) : 0

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex items-center gap-1.5 rounded-md border border-gray-200 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          <span aria-hidden>←</span> 返回历史记录
        </button>
        <span className="text-xs text-gray-500">{formatDateTime(record.timestamp)}</span>
      </div>

      <div>
        <h2 className="text-lg font-semibold text-gray-900">批改报告</h2>
        <p className="mt-1 text-sm text-gray-600">
          共 {total} 题 · 正确 {correct} · 错误 {wrong}
          {pendingReview > 0 ? ` · 待复核 ${pendingReview}` : ''} · 未作答{' '}
          {total - answered.length} · 准确率 {accuracy}%
        </p>
      </div>

      {record.questions.length > 0 ? (
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
        {filteredQuestions.length === 0 && record.questions.length > 0 && questionFilter !== 'all' ? (
          <p className="text-sm text-gray-500">没有符合当前筛选的题目。</p>
        ) : (
          filteredQuestions.map((q) => (
            <QuestionCard
              key={q.question_number}
              question={q}
              expanded={Boolean(expandedByQuestionId[q.question_number])}
              onToggleExpand={() => toggleQuestionExpand(q.question_number)}
            />
          ))
        )}
      </div>

      {record.summary ? <PageSummary summary={record.summary} /> : null}
    </div>
  )
}
