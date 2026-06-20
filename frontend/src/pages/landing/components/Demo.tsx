import { useInViewFadeIn } from '../hooks/useInViewFadeIn'

export function Demo() {
  const { ref, inView } = useInViewFadeIn<HTMLDivElement>()
  return (
    <section className="border-t border-[color:var(--color-ink-100)] bg-white py-16 sm:py-20 md:py-24">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 md:px-8">
        <header className="mb-8 md:mb-10">
          <p className="text-[12px] font-semibold uppercase tracking-[0.14em] text-[color:var(--color-ink-500)]">
            Case study
          </p>
          <h2 className="mt-2 text-[24px] font-semibold tracking-tight text-[color:var(--color-ink-950)] sm:text-3xl md:text-4xl">
            看一个真实批改案例
          </h2>
        </header>

        <div
          ref={ref}
          className={`lp-reveal ${inView ? 'lp-in' : ''} mx-auto w-full max-w-[800px]`}
        >
          <div className="overflow-hidden rounded-2xl border border-[color:var(--color-ink-200)] bg-white shadow-[0_8px_32px_-12px_rgba(15,23,42,0.16)]">
            {/* Top: question placeholder */}
            <div className="border-b border-[color:var(--color-ink-100)] bg-[color:var(--color-ink-100)]/50 px-5 py-5 sm:px-7 sm:py-7">
              <div className="mb-3 flex items-center gap-2">
                <span className="inline-flex items-center gap-1 rounded bg-white px-2 py-0.5 font-mono text-[11px] font-medium text-[color:var(--color-ink-700)] ring-1 ring-[color:var(--color-ink-200)]">
                  CAIE 9231
                </span>
                <span className="inline-flex items-center gap-1 rounded bg-white px-2 py-0.5 font-mono text-[11px] font-medium text-[color:var(--color-ink-700)] ring-1 ring-[color:var(--color-ink-200)]">
                  Probability
                </span>
              </div>
              <p className="text-[12.5px] uppercase tracking-wider text-[color:var(--color-ink-500)]">
                Question
              </p>
              <p className="mt-1 text-[14px] leading-relaxed text-[color:var(--color-ink-800)] sm:text-[15px]">
                A bag contains 10 red balls and 5 blue balls. Three balls are drawn
                without replacement. Find the probability that exactly two balls are red,
                given that at least one ball is blue.
              </p>
              <p className="mt-3 font-mono text-[11px] text-[color:var(--color-ink-500)]">
                [4 marks]
              </p>
            </div>

            {/* Bottom: grading breakdown */}
            <div className="px-5 py-6 sm:px-7 sm:py-8">
              <div className="flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-[12px] font-semibold text-emerald-700 ring-1 ring-emerald-100">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                  正确 · 3 / 4 分
                </span>
                <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-50 px-2.5 py-1 text-[12px] font-semibold text-rose-700 ring-1 ring-rose-100">
                  <WarnIcon />
                  分数未化简 −1 分
                </span>
              </div>

              <div className="mt-5 overflow-hidden rounded-lg border border-[color:var(--color-ink-200)]">
                <div className="flex items-stretch">
                  <div className="flex flex-1 items-center justify-center bg-rose-50/70 px-3 py-4 text-center">
                    <span className="font-mono text-[18px] font-semibold text-[color:var(--color-ink-900)] line-through decoration-rose-400 decoration-[2px]">
                      24 / 210
                    </span>
                  </div>
                  <div className="flex items-center bg-[color:var(--color-ink-100)] px-3 text-[color:var(--color-ink-500)]">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4">
                      <line x1="5" y1="12" x2="19" y2="12" strokeLinecap="round" />
                      <polyline points="12 5 19 12 12 19" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </div>
                  <div className="flex flex-1 items-center justify-center bg-emerald-50/70 px-3 py-4 text-center">
                    <span className="font-mono text-[18px] font-semibold text-emerald-800">
                      4 / 35
                    </span>
                  </div>
                </div>
              </div>

              <p className="mt-5 text-[14px] leading-relaxed text-[color:var(--color-ink-700)] sm:text-[15px]">
                一道 CAIE Further Math 概率题。学生答案思路正确但未化简。
                <br />
                系统识别并扣除 1 分 accuracy mark。
                <br />
                这就是 mark scheme 批改的颗粒度。
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

function WarnIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3.5 w-3.5">
      <path d="M12 9v4" strokeLinecap="round" />
      <path d="M12 17h.01" strokeLinecap="round" />
      <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
