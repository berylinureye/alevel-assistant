import { useMemo, useState } from 'react'
import { deleteRecord, loadHistory, type HistoryRecord } from '../lib/history'
import { HistoryDetail } from './HistoryDetail'

function formatDateTime(ts: number): string {
  const d = new Date(ts)
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function groupByDay(records: HistoryRecord[]): Array<{ day: string; items: HistoryRecord[] }> {
  const map = new Map<string, HistoryRecord[]>()
  for (const r of records) {
    const d = new Date(r.timestamp)
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    const arr = map.get(key) ?? []
    arr.push(r)
    map.set(key, arr)
  }
  return [...map.entries()].map(([day, items]) => ({ day, items }))
}

export function HistoryTab() {
  const [records, setRecords] = useState<HistoryRecord[]>(() => loadHistory())
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const groups = useMemo(() => groupByDay(records), [records])

  const selectedRecord = useMemo(
    () => (selectedId ? records.find((r) => r.id === selectedId) ?? null : null),
    [records, selectedId],
  )

  const handleDelete = (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm('确定删除这条记录吗？')) return
    setRecords(deleteRecord(id))
  }

  if (selectedRecord) {
    return (
      <HistoryDetail
        record={selectedRecord}
        onBack={() => setSelectedId(null)}
      />
    )
  }

  if (records.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-gray-300 bg-white p-8 text-center text-sm text-gray-500">
        还没有批改记录。完成一次批改后会自动保存在这里。
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">历史记录</h2>
        <span className="text-xs text-gray-500">共 {records.length} 次批改</span>
      </div>

      <div className="relative">
        <div className="absolute left-4 top-0 bottom-0 w-px bg-gray-200" aria-hidden />
        <div className="space-y-8">
          {groups.map(({ day, items }) => (
            <div key={day} className="space-y-3">
              <div className="relative pl-10">
                <div className="absolute left-2 top-1 h-4 w-4 rounded-full border-2 border-blue-500 bg-white" />
                <p className="text-xs font-medium text-gray-500">{day}</p>
              </div>
              {items.map((r) => {
                const answered = r.questions.filter((q) => !q.unanswered)
                const correct = answered.filter((q) => q.is_correct).length
                const pendingReview = r.questions.filter(
                  (q) => !q.unanswered && q.error_type === 'pending_review',
                ).length
                const wrong = answered.length - correct - pendingReview
                const total = r.questions.length
                const graded = answered.length - pendingReview
                const accuracy =
                  graded > 0 ? Math.round((correct / graded) * 100) : 0
                return (
                  <div key={r.id} className="relative pl-10">
                    <div className="absolute left-3 top-4 h-2 w-2 rounded-full bg-gray-400" />
                    <article
                      role="button"
                      tabIndex={0}
                      onClick={() => setSelectedId(r.id)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault()
                          setSelectedId(r.id)
                        }
                      }}
                      className="group cursor-pointer rounded-lg border border-gray-200 bg-white p-4 shadow-sm transition hover:-translate-y-0.5 hover:border-blue-300 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-blue-400"
                      aria-label={`查看 ${formatDateTime(r.timestamp)} 的批改报告`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium text-gray-900">
                            {formatDateTime(r.timestamp)}
                          </p>
                          <p className="mt-1 text-xs text-gray-500">
                            共 {total} 题 · 正确 {correct} · 错误 {wrong}
                            {pendingReview > 0 ? ` · 待复核 ${pendingReview}` : ''} · 未作答{' '}
                            {total - answered.length} · 准确率 {accuracy}%
                          </p>
                          {r.summary?.overall_teacher_comment ? (
                            <p className="mt-2 line-clamp-2 text-xs text-gray-600">
                              {r.summary.overall_teacher_comment}
                            </p>
                          ) : null}
                        </div>
                        <div className="flex shrink-0 items-center gap-2">
                          <span
                            className="rounded border border-blue-200 bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700 transition group-hover:bg-blue-100"
                            aria-hidden
                          >
                            查看 →
                          </span>
                          <button
                            type="button"
                            onClick={(e) => handleDelete(r.id, e)}
                            className="rounded border border-red-200 px-2 py-1 text-xs text-red-600 hover:bg-red-50"
                          >
                            删除
                          </button>
                        </div>
                      </div>
                    </article>
                  </div>
                )
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
