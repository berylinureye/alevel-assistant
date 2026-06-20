import type { SubmitAnswerResponse } from '../../types/practice'
import { renderLatex } from './latexUtils'

interface Props {
  result: SubmitAnswerResponse
}

export function PracticeResult({ result }: Props) {
  const { grade_result, reference_answer, marking_points } = result
  const isCorrect = grade_result.is_correct

  return (
    <div
      className={`mt-4 rounded-lg border p-4 ${
        isCorrect
          ? 'border-green-200 bg-green-50'
          : 'border-red-200 bg-red-50'
      }`}
    >
      {/* Score header */}
      <div className="mb-3 flex items-center gap-3">
        <span className={`text-2xl ${isCorrect ? 'text-green-600' : 'text-red-600'}`}>
          {isCorrect ? '✓' : '✗'}
        </span>
        <span className="text-lg font-semibold">
          {grade_result.score}/{grade_result.full_score}
        </span>
        {grade_result.error_type && (
          <span className="rounded bg-red-100 px-2 py-0.5 text-xs text-red-700">
            {grade_result.error_type}
          </span>
        )}
      </div>

      {/* Feedback */}
      <p className="mb-3 text-sm text-gray-700">{grade_result.short_feedback}</p>

      {grade_result.student_feedback && (
        <div
          className="mb-3 text-sm text-gray-600"
          dangerouslySetInnerHTML={{ __html: renderLatex(grade_result.student_feedback) }}
        />
      )}

      {/* Reference answer */}
      {reference_answer && (
        <div className="mt-3 border-t border-gray-200 pt-3">
          <p className="mb-1 text-xs font-medium text-gray-500">参考答案</p>
          <div
            className="text-sm text-gray-700"
            dangerouslySetInnerHTML={{ __html: renderLatex(reference_answer) }}
          />
        </div>
      )}

      {/* Marking points */}
      {marking_points && marking_points.length > 0 && (
        <div className="mt-3 border-t border-gray-200 pt-3">
          <p className="mb-1 text-xs font-medium text-gray-500">评分标准</p>
          <ul className="space-y-1 text-sm text-gray-600">
            {marking_points.map((mp, i) => (
              <li key={i}>- {mp}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Knowledge tags */}
      {grade_result.knowledge_tags.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1">
          {grade_result.knowledge_tags.map((tag) => (
            <span key={tag} className="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
              {tag}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
