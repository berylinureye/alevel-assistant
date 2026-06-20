export type QuestionFilter = 'all' | 'correct' | 'wrong' | 'unanswered'

const FILTERS: { key: QuestionFilter; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'correct', label: '正确' },
  { key: 'wrong', label: '错误' },
  { key: 'unanswered', label: '未作答' },
]

export interface FilterBarProps {
  filter: QuestionFilter
  onFilterChange: (f: QuestionFilter) => void
  counts: { all: number; correct: number; wrong: number; unanswered: number }
  onToggleExpandAll: () => void
  allVisibleExpanded: boolean
  hasVisibleQuestions: boolean
}

export function FilterBar({
  filter,
  onFilterChange,
  counts,
  onToggleExpandAll,
  allVisibleExpanded,
  hasVisibleQuestions,
}: FilterBarProps) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white/85 p-2 shadow-sm sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
      <div className="flex flex-wrap gap-1">
        {FILTERS.map(({ key, label }) => {
          const selected = filter === key
          const count = counts[key]
          return (
            <button
              key={key}
              type="button"
              onClick={() => onFilterChange(key)}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
                selected
                  ? 'bg-slate-950 text-white shadow-sm'
                  : 'text-slate-500 hover:bg-slate-100 hover:text-slate-800'
              }`}
            >
              {label} ({count})
            </button>
          )
        })}
      </div>
      <button
        type="button"
        onClick={onToggleExpandAll}
        disabled={!hasVisibleQuestions}
        className="shrink-0 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {allVisibleExpanded ? '全部折叠' : '全部展开'}
      </button>
    </div>
  )
}
