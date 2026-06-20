import type { ReactNode } from 'react'
import { useInViewFadeIn } from '../hooks/useInViewFadeIn'

export function Features() {
  return (
    <section className="border-t border-[color:var(--color-ink-100)] bg-white py-16 sm:py-20 md:py-24">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 md:px-8">
        <header className="mb-10 md:mb-16">
          <p className="text-[12px] font-semibold uppercase tracking-[0.14em] text-[color:var(--color-ink-500)]">
            差异化
          </p>
          <h2 className="mt-2 text-[24px] font-semibold tracking-tight text-[color:var(--color-ink-950)] sm:text-3xl md:text-4xl">
            为什么是我们
          </h2>
        </header>

        <div className="space-y-12 md:space-y-24">
          <FeatureRow
            side="left"
            kicker="卖点 1"
            title="按 CAIE mark scheme 批改，不是只判对错"
            body={
              <>
                <p>CAIE 的 mark scheme 给分到每个步骤：</p>
                <ul className="mt-2 space-y-1">
                  <li>• M1 / M2 看过程（method mark）</li>
                  <li>• A1 / B1 看结果（accuracy mark）</li>
                  <li>• 分数没化简要扣 1 分</li>
                  <li>• 单位漏写要扣</li>
                  <li>• 推导跳步 method mark 直接没</li>
                </ul>
                <p className="mt-4">
                  一般 AI 只判断"答案对不对"。
                  <br className="hidden md:block" />
                  我们拆解每一步，对照 mark scheme 的给分点逐一判定。
                </p>
              </>
            }
            visual={<FeatureVisualMarkScheme />}
          />

          <FeatureRow
            side="right"
            kicker="卖点 2"
            title="5 个模型交叉校验，不是单模型套壳"
            body={
              <>
                <p>市面上大部分 AI 批改只用一个大模型。</p>
                <p className="mt-3">
                  但大模型在数学推理上 hallucination 率不低——
                  <br />
                  "AI 说你错了但你其实对了" 是学生最崩溃的体验。
                </p>
                <p className="mt-3">
                  我们让 5 个国产大模型并行批改：
                  <br />
                  <span className="font-medium text-[color:var(--color-ink-800)]">
                    DeepSeek · Qwen-Fast · Qwen-Max · GLM-4-Plus · GLM-5.1
                  </span>
                </p>
                <p className="mt-3">
                  它们投票决定最终判分，误判率压到单模型的几分之一。
                </p>
              </>
            }
            visual={<FeatureVisualAgents />}
          />

          <FeatureRow
            side="left"
            kicker="卖点 3"
            title="错题不是看完就忘"
            badge="Coming Soon"
            body={
              <>
                <p>每道错题自动归档，按 topic 和 paper 分类。</p>
                <p className="mt-3">
                  接入 CAIE past paper 题库后，系统会推送同类题让你刷。
                  从"作业批改工具"升级成"个人学习系统"。
                </p>
                <p className="mt-3 text-[color:var(--color-ink-500)]">（题库功能开发中）</p>
              </>
            }
            visual={<FeatureVisualArchive />}
          />
        </div>
      </div>
    </section>
  )
}

function FeatureRow({
  side,
  kicker,
  title,
  body,
  visual,
  badge,
}: {
  side: 'left' | 'right'
  kicker: string
  title: string
  body: ReactNode
  visual: ReactNode
  badge?: string
}) {
  const { ref, inView } = useInViewFadeIn<HTMLDivElement>()
  // Mobile: visual on top, text below.
  // Desktop: alternate — left-visual/right-text, or reversed.
  const desktopOrder = side === 'left' ? 'md:flex-row-reverse' : 'md:flex-row'

  return (
    <div
      ref={ref}
      className={`lp-reveal ${inView ? 'lp-in' : ''} flex flex-col gap-6 md:gap-12 ${desktopOrder} md:items-center`}
    >
      <div className="md:flex-1">{visual}</div>

      <div className="md:flex-1">
        <p className="text-[12px] font-semibold uppercase tracking-[0.14em] text-[color:var(--color-brand)]">
          {kicker}
        </p>
        <h3 className="mt-2 flex flex-wrap items-center gap-2 text-[20px] font-semibold leading-snug tracking-tight text-[color:var(--color-ink-950)] sm:text-2xl md:text-[26px]">
          {title}
          {badge ? (
            <span className="inline-flex items-center rounded-full bg-[color:var(--color-amber-soft)] px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-amber-800">
              {badge}
            </span>
          ) : null}
        </h3>
        <div className="mt-4 space-y-0 text-[14.5px] leading-relaxed text-[color:var(--color-ink-700)] md:text-[15.5px]">
          {body}
        </div>
      </div>
    </div>
  )
}

/* ----- Visuals (pure CSS, no external images) ----- */

function FeatureVisualMarkScheme() {
  return (
    <div className="overflow-hidden rounded-2xl border border-[color:var(--color-ink-200)] bg-white p-5 shadow-sm md:p-6">
      <div className="mb-3 flex items-center justify-between border-b border-[color:var(--color-ink-100)] pb-3">
        <span className="text-[11px] font-semibold uppercase tracking-wide text-[color:var(--color-ink-500)]">
          Mark Scheme · 逐步判分
        </span>
        <span className="rounded bg-[color:var(--color-ink-100)] px-2 py-0.5 font-mono text-[10px] text-[color:var(--color-ink-700)]">
          9709/12
        </span>
      </div>

      <div className="space-y-3 text-[13px]">
        <StepLine tag="M1" status="ok" text="设 k = log₂ x，替换方程" />
        <StepLine tag="M1" status="ok" text="解得 k² − 3k + 2 = 0" />
        <StepLine tag="A1" status="ok" text="k = 1 或 k = 2" />
        <StepLine tag="A1" status="miss" text="仅写出 x = 2，未给出 x = 4" hint="漏一个解 −1" />
        <StepLine tag="B1" status="miss" text="未注明 x > 0 的域限制" hint="条件遗漏 −1" />
      </div>

      <div className="mt-4 flex items-center justify-between rounded-lg bg-[color:var(--color-ink-950)] px-3 py-2.5 text-[12px] text-white">
        <span className="opacity-80">题目得分</span>
        <span className="font-mono text-[15px] font-semibold">3 / 5</span>
      </div>
    </div>
  )
}

function StepLine({
  tag,
  status,
  text,
  hint,
}: {
  tag: string
  status: 'ok' | 'miss'
  text: string
  hint?: string
}) {
  const tagCls =
    status === 'ok'
      ? 'bg-emerald-50 text-emerald-700 ring-emerald-100'
      : 'bg-rose-50 text-rose-700 ring-rose-100'
  return (
    <div className="flex items-start gap-2.5">
      <span
        className={`inline-flex h-5 shrink-0 items-center rounded px-1.5 text-[10.5px] font-semibold uppercase tracking-wide ring-1 ${tagCls}`}
      >
        {tag}
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-[color:var(--color-ink-800)]">{text}</p>
        {hint ? <p className="mt-0.5 text-[11.5px] text-rose-600">{hint}</p> : null}
      </div>
    </div>
  )
}

function FeatureVisualAgents() {
  const agents = [
    { name: 'DeepSeek', color: 'bg-blue-500' },
    { name: 'Qwen-Fast', color: 'bg-violet-500' },
    { name: 'Qwen-Max', color: 'bg-indigo-500' },
    { name: 'GLM-4-Plus', color: 'bg-teal-500' },
    { name: 'GLM-5.1', color: 'bg-emerald-500' },
  ]
  return (
    <div className="rounded-2xl border border-[color:var(--color-ink-200)] bg-white p-5 shadow-sm md:p-6">
      <div className="grid grid-cols-5 gap-2.5">
        {agents.map((a) => (
          <div key={a.name} className="flex flex-col items-center gap-2">
            <span
              className={`flex h-10 w-10 items-center justify-center rounded-xl text-[12px] font-semibold text-white ${a.color}`}
              aria-hidden
            >
              {a.name.slice(0, 1)}
            </span>
            <span className="text-center text-[10px] leading-tight text-[color:var(--color-ink-600)]">
              {a.name}
            </span>
          </div>
        ))}
      </div>

      <div className="mx-auto mt-4 h-14 w-px bg-[color:var(--color-ink-200)]" aria-hidden />

      <div className="flex items-center justify-center">
        <span className="inline-flex items-center gap-2 rounded-full border border-[color:var(--color-ink-200)] bg-[color:var(--color-ink-100)] px-3 py-1.5 text-[12px] font-semibold text-[color:var(--color-ink-800)]">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3.5 w-3.5 text-emerald-600">
            <polyline points="20 6 9 17 4 12" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          投票判分 · 误判率 ↓
        </span>
      </div>
    </div>
  )
}

function FeatureVisualArchive() {
  const items = [
    { topic: 'Probability', n: 4 },
    { topic: 'Complex Numbers', n: 2 },
    { topic: 'Differentiation', n: 6 },
    { topic: 'Vectors', n: 1 },
  ]
  return (
    <div className="rounded-2xl border border-[color:var(--color-ink-200)] bg-white p-5 shadow-sm md:p-6">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-[12px] font-semibold text-[color:var(--color-ink-700)]">错题本 · 按 Topic</span>
        <span className="rounded bg-[color:var(--color-amber-soft)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-800">
          待上线
        </span>
      </div>
      <ul className="space-y-2">
        {items.map((it) => (
          <li
            key={it.topic}
            className="flex items-center justify-between rounded-lg border border-[color:var(--color-ink-100)] bg-[color:var(--color-ink-100)]/60 px-3 py-2.5"
          >
            <span className="text-[13px] font-medium text-[color:var(--color-ink-800)]">{it.topic}</span>
            <span className="font-mono text-[12px] text-[color:var(--color-ink-500)]">{it.n} 题</span>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-[11.5px] text-[color:var(--color-ink-500)]">
        接入 past paper 题库后，每个 topic 会推送同类题
      </p>
    </div>
  )
}
