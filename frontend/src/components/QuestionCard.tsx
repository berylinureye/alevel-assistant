import { useEffect, useState } from 'react'
import type { QuestionResult as QuestionResultModel } from '../types'
import { confidenceTextClass } from '../utils/confidenceStyle'
import { renderMath } from '../utils/mathRender'
import { SolutionPanel } from './SolutionPanel'
import { QuestionTranslation } from './QuestionTranslation'
import { subscribeTaxonomy, resolveChapters } from '../lib/taxonomyCache'
import type { SubtopicChapterMap } from '../lib/history'

export interface QuestionCardProps {
  question: QuestionResultModel
  expanded: boolean
  onToggleExpand: () => void
  /** 本题对应的上传页预览（object URL） */
  imageUrl?: string
}

function ImagePreview({ imageUrl, questionNumber }: { imageUrl: string; questionNumber: string }) {
  const [open, setOpen] = useState(false)
  const [previewFailed, setPreviewFailed] = useState(false)
  const [zoomed, setZoomed] = useState(false)

  // 锁定 body 滚动
  useEffect(() => {
    if (!open) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => {
      document.body.style.overflow = prev
      window.removeEventListener('keydown', onKey)
    }
  }, [open])

  useEffect(() => {
    if (open) return
    queueMicrotask(() => setZoomed(false))
  }, [open])

  const closePreview = () => {
    setOpen(false)
    setZoomed(false)
  }

  return (
    <div className="border-b border-slate-100 px-4 py-2">
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex items-center gap-1.5 text-xs text-slate-500 transition hover:text-slate-700"
      >
        <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
          <circle cx="11" cy="11" r="7" />
          <path d="m20 20-3.5-3.5" strokeLinecap="round" />
        </svg>
        点击查看原始图片
      </button>

      {open ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 backdrop-blur-sm animate-[fadeIn_0.15s_ease-out]"
          onClick={closePreview}
          role="dialog"
          aria-modal="true"
        >
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation()
              closePreview()
            }}
            className="absolute right-4 top-4 z-10 flex h-10 w-10 items-center justify-center rounded-full bg-white/10 text-2xl text-white transition hover:bg-white/20"
            aria-label="关闭"
          >
            ✕
          </button>

          <div
            className={`h-full w-full ${zoomed ? 'overflow-auto' : 'overflow-hidden flex items-center justify-center'}`}
            onClick={(e) => e.stopPropagation()}
          >
            {previewFailed ? (
              <div className="m-auto max-w-md px-4 py-6 text-center text-sm text-gray-200">
                当前浏览器无法预览这张原图，但分析仍已基于原始上传文件完成。
              </div>
            ) : (
              <img
                src={imageUrl}
                alt={`${questionNumber} 原始作业图片`}
                onClick={() => setZoomed((v) => !v)}
                onError={() => setPreviewFailed(true)}
                className={
                  zoomed
                    ? 'max-w-none cursor-zoom-out'
                    : 'mx-auto max-h-screen max-w-full cursor-zoom-in object-contain'
                }
                style={zoomed ? { width: '200%', height: 'auto' } : undefined}
              />
            )}
          </div>

          <p className="pointer-events-none absolute bottom-4 left-1/2 -translate-x-1/2 text-xs text-white/70">
            点击图片{zoomed ? '缩小' : '放大'} · 点击空白或按 Esc 关闭
          </p>
        </div>
      ) : null}
    </div>
  )
}

function confidenceLabel(value: number): string {
  if (value >= 0.85) return '高'
  if (value >= 0.65) return '中'
  return '低'
}

function confidenceReason(question: QuestionResultModel, value: number): string {
  if (question.needs_review || question.error_type === 'pending_review') {
    return '此题存在识别或判分不确定点，建议老师复核。'
  }
  if (value >= 0.85) return '答案、关键步骤和题目文本一致性较好。'
  if (value >= 0.65) return '有足够依据给出反馈，但部分步骤或手写识别仍需留意。'
  return '识别或判分依据不足，建议补充清晰题目页或让老师复核。'
}

function statusText(question: QuestionResultModel, needsTeacherReview: boolean): string {
  if (question.unanswered) return '未作答'
  if (needsTeacherReview) return '建议老师复核'
  if (question.is_correct) return '正确'
  if ((question.score ?? 0) > 0) return '部分正确'
  return '需要订正'
}

function diagnosisText(question: QuestionResultModel, needsTeacherReview: boolean): string {
  if (question.unanswered) return '这题还没有看到作答，建议先补完整答案再批改。'
  if (needsTeacherReview) return question.short_feedback || 'AI 对这题不够确定，建议老师看一眼关键步骤。'
  if (question.short_feedback) return question.short_feedback
  if (question.is_correct) return '答案和关键步骤基本一致，可以进入下一题或做同类巩固。'
  if ((question.score ?? 0) > 0) return '有部分步骤拿到分数，下一步重点补齐扣分点。'
  return '当前答案没有拿到主要分数，建议先看标准思路再重做一遍。'
}

function routeText(question: QuestionResultModel): string {
  if (question.grading_route === 'past_paper_mark_scheme') return '按评分规则批改'
  if (question.grading_route === 'open_ai_grading') return '开放批改'
  return 'AI 批改'
}

function statusPillClass(question: QuestionResultModel, needsTeacherReview: boolean): string {
  if (question.unanswered) return 'border-slate-200 bg-white text-slate-600'
  if (needsTeacherReview) return 'border-slate-300 bg-white text-slate-800'
  if (question.is_correct) return 'border-emerald-200 bg-emerald-50 text-emerald-700'
  if ((question.score ?? 0) > 0) return 'border-slate-300 bg-white text-slate-800'
  return 'border-rose-200 bg-rose-50 text-rose-700'
}

function scoreBarClass(question: QuestionResultModel, scorePct: number): string {
  if (question.unanswered) return 'bg-slate-400'
  return question.is_correct || scorePct >= 100 ? 'bg-emerald-500' : 'bg-rose-400'
}

export function QuestionCard({ question, expanded, onToggleExpand, imageUrl }: QuestionCardProps) {
  const [hasRenderedDetails, setHasRenderedDetails] = useState(expanded)

  useEffect(() => {
    if (expanded) {
      queueMicrotask(() => setHasRenderedDetails(true))
    }
  }, [expanded])

  // 防御后端返回 null 的数组字段
  const knowledgeTags = question.knowledge_tags ?? []

  const [taxonomy, setTaxonomy] = useState<SubtopicChapterMap | null>(null)
  useEffect(() => subscribeTaxonomy(setTaxonomy), [])
  const chapters = resolveChapters(knowledgeTags, taxonomy)

  // pending_review：图表题或低置信度安全网——系统无法可靠判分，标黄等老师复核。
  // 覆盖红色"错误"展示，避免学生被误判。
  const isPendingReview = question.error_type === 'pending_review'
  const gradingConfidence = question.grading_confidence ?? 0
  const aiConfidence = question.needs_review || isPendingReview
    ? Math.min(question.confidence, gradingConfidence || question.confidence, 0.6)
    : Math.min(question.confidence, gradingConfidence || question.confidence)
  const needsTeacherReview = question.needs_review || isPendingReview || aiConfidence < 0.65
  const isPartiallyCorrect = !question.is_correct && !question.unanswered && !needsTeacherReview && (question.score ?? 0) > 0
  const leftBorderClass = question.unanswered
    ? 'border-l-slate-300'
    : needsTeacherReview
      ? 'border-l-slate-500'
      : question.is_correct
        ? 'border-l-slate-950'
        : isPartiallyCorrect
          ? 'border-l-slate-700'
        : 'border-l-slate-950'
  const aiConfidenceText = confidenceLabel(aiConfidence)
  const aiConfidenceTitle = confidenceReason(question, aiConfidence)
  const scorePct = question.full_score > 0 ? Math.round(((question.score ?? 0) / question.full_score) * 100) : 0

  const relevantFormulas = question.relevant_formulas ?? []
  const showErrorAnalysisSection =
    !question.is_correct && !isPendingReview && relevantFormulas.length > 0
  const showDetails = expanded || hasRenderedDetails

  return (
    <article
      className={`animate-[fadeIn_0.3s_ease-out] relative overflow-visible rounded-xl border border-slate-200 bg-white shadow-sm ${leftBorderClass} border-l-4`}
    >
      <button
        type="button"
        onClick={onToggleExpand}
        aria-expanded={expanded}
        className="flex w-full items-start justify-between gap-3 border-b border-slate-100 p-4 text-left transition hover:bg-slate-50/80 sm:p-5"
      >
        <div className="grid min-w-0 flex-1 gap-4 sm:grid-cols-[minmax(0,1fr)_128px]">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-xl font-semibold tracking-tight text-slate-950">{question.question_number}</h3>
              <span className={`rounded-md border px-2.5 py-0.5 text-xs font-semibold ${statusPillClass(question, needsTeacherReview)}`}>
                {statusText(question, needsTeacherReview)}
              </span>
              <span className="rounded-md border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs font-semibold text-slate-600">
                {routeText(question)}
              </span>
            </div>
            <p className="mt-2 text-sm leading-6 text-slate-700 [overflow-wrap:anywhere]">
              {diagnosisText(question, needsTeacherReview)}
            </p>
            {question.short_feedback ? (
              <p className="mt-1 truncate text-sm text-slate-500">
                {question.short_feedback}
              </p>
            ) : null}
            <span
              className={`mt-2 inline-flex text-xs ${confidenceTextClass(aiConfidence)}`}
              title={aiConfidenceTitle}
            >
              AI 置信度：{aiConfidenceText}
            </span>
          </div>

          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-right">
            <p className="text-xs text-slate-500">得分</p>
            <p className="mt-1 text-2xl font-semibold text-slate-950">
              {question.score}
              <span className="text-sm font-medium text-slate-500"> / {question.full_score}</span>
            </p>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-200">
              <div className={`h-full rounded-full ${scoreBarClass(question, scorePct)}`} style={{ width: `${Math.min(100, Math.max(0, scorePct))}%` }} />
            </div>
          </div>
        </div>
        <span
          className={`mt-1 shrink-0 text-slate-400 transition-transform ${expanded ? 'rotate-180' : ''}`}
          aria-hidden
        >
          ▼
        </span>
      </button>

      {showDetails ? (
        <div className={expanded ? '' : 'hidden'} aria-hidden={!expanded}>
          {imageUrl ? (
            <ImagePreview imageUrl={imageUrl} questionNumber={question.question_number} />
          ) : null}
          <div className="border-b border-slate-100 p-4 sm:p-5">
            <h4 className="mb-3 text-xs font-semibold text-slate-500">题目</h4>
            {question.parent_stem ? (
              <div className="mb-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                <div className="mb-1 text-[11px] font-semibold text-slate-500">
                  主题干
                </div>
                <p
                  className="whitespace-pre-wrap text-sm leading-relaxed text-slate-900 overflow-x-auto [overflow-wrap:anywhere] [&_.katex]:text-inherit"
                  dangerouslySetInnerHTML={{ __html: renderMath(question.parent_stem) }}
                />
              </div>
            ) : null}
            {question.question_text ? (
              <div className={question.parent_stem ? 'rounded-lg bg-slate-50 px-3 py-2' : ''}>
                {question.parent_stem ? (
                  <div className="mb-1 text-[11px] font-semibold text-slate-500">
                    本小题（{question.question_number}）
                  </div>
                ) : null}
                <p
                  className="whitespace-pre-wrap text-sm text-slate-900 overflow-x-auto [overflow-wrap:anywhere] [&_.katex]:text-inherit"
                  dangerouslySetInnerHTML={{ __html: renderMath(question.question_text) }}
                />
              </div>
            ) : null}
          </div>

          <QuestionTranslation
            questionText={
              question.parent_stem
                ? `${question.parent_stem}\n\n${question.question_text}`
                : question.question_text
            }
          />

          <div className="border-b border-slate-100 p-4 sm:p-5">
            <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
              <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 px-4 py-3">
                <div className="min-w-0">
                  <p className="text-xs font-semibold text-slate-500">
                    错题订正
                  </p>
                  <p className="mt-1 text-sm font-medium text-slate-950">
                    先看扣分点，再决定追问或重做
                  </p>
                </div>
                <span className={`rounded-md border px-2.5 py-0.5 text-xs font-semibold ${statusPillClass(question, needsTeacherReview)}`}>
                  {statusText(question, needsTeacherReview)}
                </span>
              </div>

              <div className="grid divide-y divide-slate-100 sm:grid-cols-4 sm:divide-x sm:divide-y-0">
                <div className="px-4 py-3">
                  <p className="text-xs text-slate-500">本题表现</p>
                  <p className="mt-1 text-sm font-semibold text-slate-900">
                    {statusText(question, needsTeacherReview)}
                  </p>
                </div>
                <div className="px-4 py-3">
                  <p className="text-xs text-slate-500">得分</p>
                  <p className="mt-1 text-sm font-semibold text-slate-900">
                    {question.score} / {question.full_score} 分
                  </p>
                </div>
                <div className="px-4 py-3">
                  <p className="text-xs text-slate-500">批改依据</p>
                  <p className="mt-1 text-sm font-semibold text-slate-900">
                    {routeText(question)}
                  </p>
                </div>
                <div className="px-4 py-3">
                  <p className="text-xs text-slate-500">AI 置信度</p>
                  <p className={`mt-1 text-sm font-semibold ${confidenceTextClass(aiConfidence)}`}>
                    {aiConfidenceText}
                  </p>
                </div>
              </div>

              <div className="border-t border-slate-100 bg-slate-50/70 px-4 py-3">
                <p className="text-sm leading-6 text-slate-700 [overflow-wrap:anywhere]">
                  {diagnosisText(question, needsTeacherReview)}
                </p>
              {question.mark_scheme_context_error ? (
                <p className="mt-2 rounded-md border border-slate-200 bg-white/70 px-3 py-2 text-xs leading-5 text-slate-700">
                  评分规则上下文不足：{question.mark_scheme_context_error}
                </p>
              ) : null}
              </div>
            </div>

            <div className="mt-4 grid gap-3 lg:grid-cols-2">
              <div>
                <h4 className="mb-2 text-xs font-semibold text-slate-500">学生作答</h4>
                {question.unanswered ? (
                  <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500">
                    此题学生未作答。
                  </div>
                ) : (
                  <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5">
                    <div
                      className="whitespace-pre-wrap text-sm text-slate-900 overflow-x-auto [overflow-wrap:anywhere] [&_.katex]:text-inherit"
                      dangerouslySetInnerHTML={{ __html: renderMath(question.student_answer) }}
                    />
                  </div>
                )}
              </div>
              {question.correct_answer != null && question.correct_answer !== '' ? (
                <div>
                  <h4 className="mb-2 text-xs font-semibold text-slate-500">参考答案</h4>
                  <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5">
                    <div
                      className="whitespace-pre-wrap text-sm font-medium text-slate-950 overflow-x-auto [overflow-wrap:anywhere] [&_.katex]:text-inherit"
                      dangerouslySetInnerHTML={{ __html: renderMath(question.correct_answer) }}
                    />
                  </div>
                </div>
              ) : null}
            </div>

            {question.detail_deductions && question.detail_deductions.length > 0 ? (
              <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5">
                <p className="mb-1.5 text-xs font-medium text-slate-600">细节失分</p>
                <div className="flex flex-wrap gap-1.5">
                  {question.detail_deductions.map((d, i) => (
                    <span
                      key={i}
                      className="inline-flex items-center gap-1 rounded-full bg-white px-2.5 py-0.5 text-xs font-medium text-slate-900 ring-1 ring-slate-200"
                      title={d.detail}
                    >
                      <span>{d.tag}</span>
                      {d.lost_points > 0 ? (
                        <span className="text-[10px] text-slate-600">−{d.lost_points}分</span>
                      ) : null}
                    </span>
                  ))}
                </div>
                {question.detail_deductions.map((d, i) => (
                  <p
                    key={`detail-${i}`}
                    className="mt-1.5 whitespace-pre-wrap text-xs text-slate-700 [overflow-wrap:anywhere] [&_.katex]:text-inherit"
                    dangerouslySetInnerHTML={{ __html: renderMath(d.detail) }}
                  />
                ))}
              </div>
            ) : null}
            {chapters.length > 0 ? (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {chapters.map((ch) => (
                  <span
                    key={ch}
                    className="rounded-md border border-dashed border-slate-300 bg-white px-3 py-0.5 text-xs text-slate-700"
                  >
                    {ch}
                  </span>
                ))}
              </div>
            ) : null}
          </div>

          {showErrorAnalysisSection ? (
            <div className="space-y-4 border-b border-slate-100 p-4">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">错误分析</h4>

{relevantFormulas.length > 0 ? (
                <div>
                  <p className="mb-1.5 text-xs font-medium text-slate-500">应掌握的公式</p>
                  <div className="space-y-2">
                    {relevantFormulas.map((f, i) => (
                      <div
                        key={i}
                        className="max-w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-950 overflow-x-auto [overflow-wrap:anywhere] [&_.katex]:text-inherit [&_.katex-display]:my-1 [&_.katex-display]:overflow-x-auto"
                        dangerouslySetInnerHTML={{ __html: renderMath(f) }}
                      />
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}

          <SolutionPanel question={question} />

        </div>
      ) : null}
    </article>
  )
}
