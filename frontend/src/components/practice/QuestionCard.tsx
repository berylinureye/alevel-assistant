import type { QuestionBankItem } from '../../types/practice'
import { renderLatex } from './latexUtils'

const SESSION_LABELS: Record<string, string> = {
  s: '夏季',
  w: '冬季',
  m: '春季',
}

interface Props {
  question: QuestionBankItem
  index: number
  total: number
  children?: React.ReactNode
}

export function PracticeQuestionCard({ question, index, total, children }: Props) {
  const source = question.year
    ? `${question.year} ${SESSION_LABELS[question.session ?? ''] ?? ''} Paper ${question.paper_num} V${question.variant}`
    : null
  const parentStem = question.parent_stem?.trim()
  const diagramDescription = question.diagram_description?.trim()

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
      {/* Header */}
      <div className="mb-4 flex items-start justify-between">
        <div>
          <span className="text-sm font-medium text-gray-500">
            第 {index + 1}/{total} 题
          </span>
          <h3 className="text-lg font-semibold text-gray-800">
            Q{question.question_number}
          </h3>
        </div>
        <div className="flex items-center gap-2">
          <span className="rounded bg-blue-50 px-2 py-0.5 text-xs text-blue-700">
            {question.topic}
          </span>
          <span className="rounded bg-amber-50 px-2 py-0.5 text-xs text-amber-700">
            {question.marks} 分
          </span>
          <span className="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
            难度 {'★'.repeat(question.difficulty)}{'☆'.repeat(5 - question.difficulty)}
          </span>
        </div>
      </div>

      {/* Parent stem / shared context */}
      {(parentStem || diagramDescription) && (
        <div className="mb-4 border-l-4 border-blue-200 bg-blue-50/70 px-4 py-3">
          {parentStem && (
            <div>
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-blue-700">
                题干 / 已知条件
              </p>
              <div
                className="prose prose-sm max-w-none text-gray-700"
                dangerouslySetInnerHTML={{ __html: renderLatex(parentStem) }}
              />
            </div>
          )}
          {diagramDescription && (
            <div className={parentStem ? 'mt-3 border-t border-blue-100 pt-3' : ''}>
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-blue-700">
                图表信息
              </p>
              <div
                className="prose prose-sm max-w-none text-gray-700"
                dangerouslySetInnerHTML={{ __html: renderLatex(diagramDescription) }}
              />
            </div>
          )}
        </div>
      )}

      {/* Question text */}
      {(parentStem || diagramDescription) && (
        <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">
          本小问
        </p>
      )}
      <div
        className="prose prose-sm mb-4 max-w-none text-gray-700"
        dangerouslySetInnerHTML={{ __html: renderLatex(question.question_text) }}
      />

      {/* Source */}
      {source && (
        <p className="mb-4 text-xs text-gray-400">
          来源: 9709 {source} - Q{question.question_number}
        </p>
      )}

      {/* Answer area (injected) */}
      {children}
    </div>
  )
}
