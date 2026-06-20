import { useInViewFadeIn } from '../hooks/useInViewFadeIn'

const GENERIC_POINTS = [
  '只判断答案对错',
  '单模型推理，错了就错了',
  '不懂 method mark 和 accuracy mark 的区别',
  '数学推理 hallucination 率高',
  '讲解是通用的，不针对 CAIE 体系',
]

const OUR_POINTS = [
  '区分 method mark (M1/M2) 和 accuracy mark (A1)',
  '5 个国产大模型交叉校验，投票判分',
  '识别细节失分：分数未化简、单位缺失、步骤跳跃',
  '讲解对齐 CAIE past paper 的标准解题路径',
  '错题配置多种解法（代数法 / 几何法 / 标准公式法）',
]

export function Comparison() {
  const { ref, inView } = useInViewFadeIn<HTMLDivElement>()
  return (
    <section className="bg-[color:var(--color-ink-100)]/50 py-16 sm:py-20 md:py-24">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 md:px-8">
        <header className="mb-10 md:mb-12">
          <p className="text-[12px] font-semibold uppercase tracking-[0.14em] text-[color:var(--color-ink-500)]">
            为什么不一样
          </p>
          <h2 className="mt-2 text-[24px] font-semibold tracking-tight text-[color:var(--color-ink-950)] sm:text-3xl md:text-4xl">
            为什么 AI 能懂 mark scheme
          </h2>
        </header>

        <div ref={ref} className={`lp-reveal ${inView ? 'lp-in' : ''} grid gap-4 md:grid-cols-2 md:gap-6`}>
          {/* Card 1 — generic AI */}
          <div className="rounded-2xl border border-[color:var(--color-ink-200)] bg-white p-6 md:p-7">
            <div className="flex items-center gap-2">
              <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-[color:var(--color-ink-100)] text-[color:var(--color-ink-500)]">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3.5 w-3.5">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="8" y1="12" x2="16" y2="12" strokeLinecap="round" />
                </svg>
              </span>
              <h3 className="text-[16px] font-semibold text-[color:var(--color-ink-700)] md:text-[17px]">
                一般的 AI 批改
              </h3>
            </div>
            <ul className="mt-4 space-y-2.5">
              {GENERIC_POINTS.map((p) => (
                <li key={p} className="flex items-start gap-2.5 text-[14px] leading-relaxed text-[color:var(--color-ink-600)] md:text-[14.5px]">
                  <CrossIcon />
                  <span>{p}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Card 2 — ours */}
          <div className="relative rounded-2xl border border-[color:var(--color-ink-950)] bg-[color:var(--color-ink-950)] p-6 text-white md:p-7">
            <div className="flex items-center gap-2">
              <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-[color:var(--color-brand)] text-white">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="h-3.5 w-3.5">
                  <polyline points="20 6 9 17 4 12" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </span>
              <h3 className="text-[16px] font-semibold md:text-[17px]">
                按 CAIE mark scheme 批改
              </h3>
            </div>
            <ul className="mt-4 space-y-2.5">
              {OUR_POINTS.map((p) => (
                <li key={p} className="flex items-start gap-2.5 text-[14px] leading-relaxed text-white/85 md:text-[14.5px]">
                  <CheckIcon />
                  <span>{p}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <p className="mt-8 max-w-3xl text-[12.5px] leading-relaxed text-[color:var(--color-ink-500)] md:mt-10 md:text-[13px]">
          所有设计基于对 CAIE Mathematics (9709) 和 Further Mathematics (9231) syllabus 的逐条拆解。
        </p>
      </div>
    </section>
  )
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400">
      <polyline points="20 6 9 17 4 12" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function CrossIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="mt-0.5 h-4 w-4 shrink-0 text-[color:var(--color-ink-400)]">
      <line x1="6" y1="6" x2="18" y2="18" strokeLinecap="round" />
      <line x1="18" y1="6" x2="6" y2="18" strokeLinecap="round" />
    </svg>
  )
}
