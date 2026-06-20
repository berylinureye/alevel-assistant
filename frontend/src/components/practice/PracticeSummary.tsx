import type { PracticeQuestionState } from '../../types/practice'

interface Props {
  states: PracticeQuestionState[]
  onRestart: () => void
}

export function PracticeSummary({ states, onRestart }: Props) {
  const submitted = states.filter((s) => s.submitted && s.result)
  const correct = submitted.filter((s) => s.result!.grade_result.is_correct).length
  const totalScore = submitted.reduce((a, s) => a + (s.result?.grade_result.score ?? 0), 0)
  const fullScore = submitted.reduce((a, s) => a + (s.result?.grade_result.full_score ?? 0), 0)
  const pct = fullScore > 0 ? Math.round((totalScore / fullScore) * 100) : 0

  // Topic breakdown
  const topicMap = new Map<string, { correct: number; total: number }>()
  for (const s of submitted) {
    const topic = s.question.topic
    const entry = topicMap.get(topic) ?? { correct: 0, total: 0 }
    entry.total += 1
    if (s.result!.grade_result.is_correct) entry.correct += 1
    topicMap.set(topic, entry)
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
      <h2 className="mb-4 text-xl font-bold text-gray-800">练习总结</h2>

      {/* Score overview */}
      <div className="mb-6 grid grid-cols-1 gap-4 text-center sm:grid-cols-3">
        <div className="rounded-lg bg-blue-50 p-4">
          <p className="text-2xl font-bold text-blue-700">{totalScore}/{fullScore}</p>
          <p className="text-xs text-gray-500">总得分</p>
        </div>
        <div className="rounded-lg bg-green-50 p-4">
          <p className="text-2xl font-bold text-green-700">{correct}/{submitted.length}</p>
          <p className="text-xs text-gray-500">正确数</p>
        </div>
        <div className={`rounded-lg p-4 ${pct >= 70 ? 'bg-green-50' : pct >= 50 ? 'bg-amber-50' : 'bg-red-50'}`}>
          <p className={`text-2xl font-bold ${pct >= 70 ? 'text-green-700' : pct >= 50 ? 'text-amber-700' : 'text-red-700'}`}>
            {pct}%
          </p>
          <p className="text-xs text-gray-500">正确率</p>
        </div>
      </div>

      {/* Topic breakdown */}
      {topicMap.size > 0 && (
        <div className="mb-6">
          <h3 className="mb-2 text-sm font-medium text-gray-700">知识点表现</h3>
          <div className="space-y-2">
            {[...topicMap.entries()].map(([topic, { correct: c, total: t }]) => (
              <div key={topic} className="flex items-center gap-3">
                <span className="w-40 truncate text-sm text-gray-600">{topic}</span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-gray-100">
                  <div
                    className={`h-full rounded-full ${c === t ? 'bg-green-500' : c > 0 ? 'bg-amber-400' : 'bg-red-400'}`}
                    style={{ width: `${(c / t) * 100}%` }}
                  />
                </div>
                <span className="text-xs text-gray-500">{c}/{t}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Weak areas */}
      {[...topicMap.entries()].filter(([, { correct: c, total: t }]) => c < t).length > 0 && (
        <div className="mb-6 rounded-lg bg-amber-50 p-3">
          <p className="text-sm font-medium text-amber-800">需要加强的知识点:</p>
          <ul className="mt-1 text-sm text-amber-700">
            {[...topicMap.entries()]
              .filter(([, { correct: c, total: t }]) => c < t)
              .map(([topic]) => (
                <li key={topic}>- {topic}</li>
              ))}
          </ul>
        </div>
      )}

      <button
        type="button"
        onClick={onRestart}
        className="w-full rounded-md bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700"
      >
        再来一组
      </button>
    </div>
  )
}
