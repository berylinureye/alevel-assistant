import type { LargePdfPaperResolution } from '../../types'

interface PaperContextCardProps {
  resolution: LargePdfPaperResolution
  paperCode: string
  questionNumbers: string
  disabled?: boolean
  onPaperCodeChange: (value: string) => void
  onQuestionNumbersChange: (value: string) => void
}

const confidenceLabels: Record<string, string> = {
  high: '高',
  medium: '中',
  low: '低',
}

const sourceLabels: Record<string, string> = {
  cover: '封面',
  page_header: '页眉',
  question_text: '题目文本',
  manual: '手动填写',
  none: '暂无',
}

export function PaperContextCard({
  resolution,
  paperCode,
  questionNumbers,
  disabled = false,
  onPaperCodeChange,
  onQuestionNumbersChange,
}: PaperContextCardProps) {
  const confidence = resolution.match_confidence ?? 'low'
  const confidenceText = confidenceLabels[confidence] ?? '低'
  const sourceText = resolution.match_source ? sourceLabels[resolution.match_source] ?? resolution.match_source : '暂无'
  const routeText =
    resolution.grading_route === 'past_paper_mark_scheme'
      ? '按评分标准批改'
      : '开放 AI 批改'

  return (
    <section className="rounded-lg border border-slate-200 bg-slate-50/70 p-4">
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(280px,0.85fr)]">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-blue-700">卷子识别</p>
          <h3 className="mt-1 text-lg font-semibold text-slate-950">
            {resolution.paper_label || '暂未定位具体卷子'}
          </h3>
          <p className="mt-1 text-sm leading-6 text-slate-500">
            {resolution.needs_user_confirmation
              ? '系统找到了可能的卷子信息，开始批改前建议确认 paper code。'
              : '可以继续选择页面。若你知道 paper code，填写后会更稳定。'}
          </p>

          <div className="mt-4 grid gap-2 sm:grid-cols-3">
            <div className="rounded-md border border-slate-200 bg-white px-3 py-2">
              <p className="text-[11px] font-medium text-slate-500">AI 置信度</p>
              <p className="mt-0.5 text-sm font-semibold text-slate-900">{confidenceText}</p>
            </div>
            <div className="rounded-md border border-slate-200 bg-white px-3 py-2">
              <p className="text-[11px] font-medium text-slate-500">匹配来源</p>
              <p className="mt-0.5 text-sm font-semibold text-slate-900">{sourceText}</p>
            </div>
            <div className="rounded-md border border-slate-200 bg-white px-3 py-2">
              <p className="text-[11px] font-medium text-slate-500">批改路径</p>
              <p className="mt-0.5 text-sm font-semibold text-slate-900">{routeText}</p>
            </div>
          </div>
        </div>

        <div className="grid gap-3">
          <label className="block">
            <span className="text-xs font-medium text-slate-600">Paper code（可选）</span>
            <input
              type="text"
              value={paperCode}
              onChange={(e) => onPaperCodeChange(e.target.value)}
              disabled={disabled}
              placeholder="例如 9709/12/M/J/22"
              className="mt-1 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-100 disabled:cursor-not-allowed disabled:bg-slate-100"
            />
          </label>
          <label className="block">
            <span className="text-xs font-medium text-slate-600">题号（可选）</span>
            <input
              type="text"
              value={questionNumbers}
              onChange={(e) => onQuestionNumbersChange(e.target.value)}
              disabled={disabled}
              placeholder="例如 3, 4(a), 7"
              className="mt-1 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-100 disabled:cursor-not-allowed disabled:bg-slate-100"
            />
          </label>
        </div>
      </div>
    </section>
  )
}
