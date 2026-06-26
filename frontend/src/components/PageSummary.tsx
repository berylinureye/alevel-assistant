import type { PageSummary as PageSummaryData } from '../types'
import { renderMath } from '../utils/mathRender'

function scoreRatePercent(summary: PageSummaryData): number {
  const full = summary.full_score_total ?? 0
  const score = summary.score_total ?? 0
  if (full <= 0) return 0
  const pct = (score / full) * 100
  return Number.isFinite(pct) ? pct : 0
}

/** A-Level 参考等级（按得分率） */
function gradeFromPercent(p: number): string {
  if (p >= 90) return 'A*'
  if (p >= 80) return 'A'
  if (p >= 70) return 'B'
  if (p >= 60) return 'C'
  if (p >= 50) return 'D'
  if (p >= 40) return 'E'
  return 'U'
}

function ringStrokeClass(pct: number): string {
  return pct >= 100 ? 'stroke-emerald-500' : 'stroke-rose-400'
}

function scoreRateTextClass(pct: number): string {
  return pct >= 100 ? 'text-emerald-800' : 'text-rose-700'
}

function scoreRateBadgeClass(pct: number): string {
  return pct >= 100 ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'
}

/** SVG 环形进度条（得分率），圆心为百分比与等级标签 */
function ScoreRing({ percentage, grade }: { percentage: number; grade: string }) {
  const size = 128
  const strokeWidth = 10
  const r = (size - strokeWidth) / 2
  const cx = size / 2
  const cy = size / 2
  const circumference = 2 * Math.PI * r
  const clamped = Math.min(100, Math.max(0, percentage))
  const dashOffset = circumference * (1 - clamped / 100)
  const displayPct = Math.round(clamped)

  return (
    <div className="relative flex h-32 w-32 shrink-0 items-center justify-center">
      <svg
        width={size}
        height={size}
        className="-rotate-90"
        role="img"
        aria-label={`得分率 ${displayPct}%，参考等级 ${grade}`}
      >
        <circle
          cx={cx}
          cy={cy}
          r={r}
          fill="none"
          className="stroke-slate-200"
          strokeWidth={strokeWidth}
        />
        <circle
          cx={cx}
          cy={cy}
          r={r}
          fill="none"
          className={ringStrokeClass(clamped)}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={`${circumference}`}
          strokeDashoffset={dashOffset}
        />
      </svg>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center gap-0.5">
        <div className="flex items-baseline gap-1">
          <span className={`text-2xl font-bold tabular-nums ${scoreRateTextClass(clamped)}`}>{displayPct}%</span>
          <span className={`rounded-md px-1.5 py-0.5 text-xs font-semibold ${scoreRateBadgeClass(clamped)}`}>
            {grade}
          </span>
        </div>
        <span className="text-[10px] text-slate-500">得分率</span>
      </div>
    </div>
  )
}

export interface PageSummaryProps {
  /** 流式分析未返回汇总前为 null，显示骨架屏 */
  summary: PageSummaryData | null
}

function PageSummarySkeleton() {
  return (
    <section
      className="animate-pulse rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
      aria-busy="true"
      aria-label="学习诊断加载中"
    >
      <div className="mb-4 h-7 w-28 rounded bg-slate-200" />
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:gap-8">
        <div className="h-32 w-32 shrink-0 rounded-full bg-slate-200" />
        <div className="min-w-0 flex-1 space-y-3 pt-2">
          <div className="h-4 w-12 rounded bg-slate-200" />
          <div className="h-9 w-40 rounded bg-slate-200" />
        </div>
      </div>
      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[0, 1, 2, 3].map((k) => (
          <div key={k} className="h-[4.25rem] rounded-md bg-slate-100" />
        ))}
      </div>
      <div className="mb-6 space-y-2">
        <div className="h-4 w-32 rounded bg-slate-200" />
        <div className="h-10 w-full rounded-md bg-slate-100" />
      </div>
      <div className="mb-4 h-4 w-3/4 max-w-md rounded bg-slate-100" />
      <div className="space-y-2">
        <div className="h-4 w-24 rounded bg-slate-200" />
        <div className="h-20 w-full rounded-md bg-slate-100" />
      </div>
    </section>
  )
}

export function PageSummary({ summary }: PageSummaryProps) {
  if (summary == null) {
    return <PageSummarySkeleton />
  }

  const ratePct = scoreRatePercent(summary)
  const grade = gradeFromPercent(ratePct)

  const c = summary.correct_count
  const ic = summary.incorrect_count
  const ua = summary.unanswered_count ?? 0
  const countSum = c + ic + ua
  const topProblem =
    (summary.priority_topics ?? [])[0]?.subtopic ||
    (summary.priority_topics ?? [])[0]?.topic ||
    (summary.common_error_types ?? [])[0] ||
    (summary.incorrect_count > 0 ? '请先查看错题卡片中的一句话错因' : '本次没有明显薄弱点')
  const nextAction =
    summary.incorrect_count > 0 || ua > 0
      ? `先复盘 ${topProblem}，预计用 ${summary.estimated_review_minutes ?? 0} 分钟，再做 3 道同主题练习。`
      : '保持当前节奏，建议用同主题 exam-style 题巩固速度和书写规范。'

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="mt-1 text-xl font-semibold text-slate-950">详细报告</h2>
          <p className="mt-1 text-sm leading-6 text-slate-600">
            展开分数依据、薄弱主题和教师总评。
          </p>
        </div>
        <span className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-semibold text-slate-700">
          预计复习 {summary.estimated_review_minutes ?? 0} 分钟
        </span>
      </div>

      <div className="mb-6 flex flex-col gap-4 rounded-xl border border-slate-200 bg-slate-50 p-4 sm:flex-row sm:items-center sm:gap-8">
        <ScoreRing percentage={ratePct} grade={grade} />
        <div className="min-w-0 flex-1">
          <p className="mb-1 text-xs font-semibold text-slate-500">本次表现</p>
          <div className="text-2xl font-bold text-slate-950">
            {summary.score_total} / {summary.full_score_total}
            <span className="ml-2 text-sm font-normal text-slate-500">分</span>
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-600">{nextAction}</p>
        </div>
      </div>

      <div className={`mb-6 grid gap-3 ${ua > 0 ? 'grid-cols-2 sm:grid-cols-4' : 'grid-cols-3'}`}>
        <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-center">
          <div className="text-2xl font-bold text-slate-950">{summary.total_questions}</div>
          <div className="text-xs text-slate-500">总题数</div>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-center">
          <div className="text-2xl font-bold text-slate-950">{summary.correct_count}</div>
          <div className="text-xs text-slate-500">正确</div>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-center">
          <div className="text-2xl font-bold text-slate-950">{summary.incorrect_count}</div>
          <div className="text-xs text-slate-500">错误</div>
        </div>
        {ua > 0 ? (
          <div className="rounded-lg border border-slate-200 bg-slate-100 px-3 py-2 text-center">
            <div className="text-2xl font-bold text-slate-600">{ua}</div>
            <div className="text-xs text-slate-500">未作答</div>
          </div>
        ) : null}
      </div>

      <div className="mb-6 grid gap-4 rounded-xl border border-slate-200 bg-white p-4 md:grid-cols-2">
        <div>
          <h3 className="text-xs font-semibold text-slate-500">主要问题</h3>
          <p className="mt-2 text-sm leading-6 text-slate-800">{topProblem}</p>
          {(summary.review_count ?? 0) > 0 ? (
            <p className="mt-1 text-xs text-slate-600">
              有 {summary.review_count} 道题建议老师复核，优先看这些题。
            </p>
          ) : null}
        </div>
        <div>
          <h3 className="text-xs font-semibold text-slate-500">下一步</h3>
          <p className="mt-2 text-sm leading-6 text-slate-800">{nextAction}</p>
        </div>
      </div>

      <div className="mb-6">
        <h3 className="mb-2 text-xs font-semibold text-slate-500">答题情况分布</h3>
        {countSum > 0 ? (
          <div className="flex h-10 w-full overflow-hidden rounded-lg text-xs font-semibold text-white shadow-inner">
            {c > 0 ? (
              <div
                className="flex min-w-0 items-center justify-center bg-slate-950 px-1"
                style={{ flex: c }}
              >
                {c}
              </div>
            ) : null}
            {ic > 0 ? (
              <div
                className="flex min-w-0 items-center justify-center bg-slate-600 px-1"
                style={{ flex: ic }}
              >
                {ic}
              </div>
            ) : null}
            {ua > 0 ? (
              <div
                className="flex min-w-0 items-center justify-center bg-slate-400 px-1"
                style={{ flex: ua }}
              >
                {ua}
              </div>
            ) : null}
          </div>
        ) : (
          <div className="flex h-10 w-full items-center justify-center rounded-md bg-slate-100 text-xs text-slate-500">
            暂无统计数据
          </div>
        )}
      </div>

      <p className="mb-4 text-sm text-slate-600">
        {summary.total_questions} 道题 · {summary.correct_count} 正确 · {summary.incorrect_count} 错误{ua > 0 ? ` · ${ua} 未作答` : ''}
      </p>

      {(summary.common_error_types ?? []).length > 0 ? (
        <div className="mb-4">
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">常见错误类型</h3>
          <div className="flex flex-wrap gap-2">
            {(summary.common_error_types ?? []).map((t) => (
              <span
                key={t}
                className="rounded-md bg-slate-100 px-3 py-1 text-xs font-medium text-slate-800"
              >
                {t}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {(summary.priority_topics ?? []).length > 0 ? (
        <div className="mb-4">
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">优先复习主题</h3>
          <div className="space-y-2">
            {summary.priority_topics.slice(0, 3).map((topic, idx) => (
              <div key={`${topic.chapter}-${topic.topic}-${topic.subtopic}-${idx}`} className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
                <p className="text-sm font-medium text-slate-950">
                  {topic.subtopic || topic.topic || '未命名主题'}
                  <span className="ml-2 text-xs font-normal text-slate-500">
                    错题 {topic.error_count} 道
                  </span>
                </p>
                {topic.chapter ? (
                  <p className="mt-0.5 text-xs text-slate-500">{topic.chapter}</p>
                ) : null}
                {(topic.key_formulas ?? []).length > 0 ? (
                  <div className="mt-2">
                    <p className="mb-1 text-xs text-slate-500">关键公式</p>
                    <div className="flex flex-wrap gap-1.5">
                      {(topic.key_formulas ?? []).map((formula, formulaIdx) => (
                        <span
                          key={`${formulaIdx}-${formula}`}
                          className="rounded-md bg-white px-2 py-1 text-xs text-slate-700 shadow-sm [&_.katex]:text-inherit"
                          dangerouslySetInnerHTML={{ __html: renderMath(formula) }}
                        />
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {summary.overall_teacher_comment !== '' ? (
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">教师总评</h3>
          <blockquote
            className="border-l-4 border-slate-300 bg-slate-50 py-3 pl-4 pr-3 text-sm italic text-slate-800 [&_.katex]:text-inherit"
            dangerouslySetInnerHTML={{ __html: renderMath(summary.overall_teacher_comment) }}
          />
        </div>
      ) : null}
    </section>
  )
}
