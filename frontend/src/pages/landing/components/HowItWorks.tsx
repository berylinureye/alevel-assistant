import { useInViewFadeIn } from '../hooks/useInViewFadeIn'

const STEPS = [
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" className="h-6 w-6">
        <path d="M23 19a2 2 0 01-2 2H3a2 2 0 01-2-2V8a2 2 0 012-2h4l2-3h6l2 3h4a2 2 0 012 2z" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="12" cy="13" r="4" />
      </svg>
    ),
    n: '01',
    title: '拍一张',
    body: '整页作业直接拍，系统自动切题。JPG / PNG / PDF 都支持。',
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" className="h-6 w-6">
        <circle cx="5" cy="12" r="2" />
        <circle cx="10" cy="12" r="2" />
        <circle cx="15" cy="12" r="2" />
        <circle cx="20" cy="12" r="2" />
        <path d="M5 12h15" strokeLinecap="round" strokeDasharray="1 3" />
      </svg>
    ),
    n: '02',
    title: '5 个 AI 同时看',
    body: 'DeepSeek / Qwen / GLM 交叉校验，避免单模型误判。一道题通常 10 秒内。',
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" className="h-6 w-6">
        <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="9" cy="10" r="0.5" fill="currentColor" />
        <circle cx="13" cy="10" r="0.5" fill="currentColor" />
        <circle cx="17" cy="10" r="0.5" fill="currentColor" />
      </svg>
    ),
    n: '03',
    title: '不懂就问 AI 老师',
    body: '错题自动配讲解，不懂的直接追问。代数法、几何法、公式法多种思路一起给。',
  },
]

export function HowItWorks() {
  const { ref, inView } = useInViewFadeIn<HTMLDivElement>()
  return (
    <section
      id="how-it-works"
      className="border-t border-[color:var(--color-ink-100)] bg-white py-16 sm:py-20 md:py-24"
    >
      <div className="mx-auto max-w-6xl px-4 sm:px-6 md:px-8">
        <div ref={ref} className={`lp-reveal ${inView ? 'lp-in' : ''}`}>
          <h2 className="text-[24px] font-semibold tracking-tight text-[color:var(--color-ink-950)] sm:text-3xl md:text-4xl">
            三步搞定一整页作业
          </h2>
          <p className="mt-3 max-w-2xl text-[14px] leading-relaxed text-[color:var(--color-ink-600)] sm:text-base">
            从拍照到看懂讲解，通常不到一分钟。
          </p>

          <ol className="mt-8 grid gap-4 md:mt-12 md:grid-cols-3 md:gap-6">
            {STEPS.map((s) => {
              const isAccent = s.n === '03'
              return (
                <li
                  key={s.n}
                  className={`relative rounded-xl border bg-white p-5 transition hover:-translate-y-0.5 hover:shadow-md md:p-6 ${
                    isAccent
                      ? 'border-[color:var(--color-brand)] shadow-[0_8px_24px_-12px_rgba(37,99,235,0.25)]'
                      : 'border-[color:var(--color-ink-200)]'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={`flex h-10 w-10 items-center justify-center rounded-lg ${
                        isAccent
                          ? 'bg-[color:var(--color-brand-soft)] text-[color:var(--color-brand)]'
                          : 'bg-[color:var(--color-ink-100)] text-[color:var(--color-ink-800)]'
                      }`}
                    >
                      {s.icon}
                    </span>
                    <span className="font-mono text-[12px] font-medium text-[color:var(--color-ink-400)]">
                      {s.n}
                    </span>
                    {isAccent ? (
                      <span className="ml-auto inline-flex items-center rounded-full bg-[color:var(--color-brand-soft)] px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide text-[color:var(--color-brand-hover)]">
                        最受欢迎
                      </span>
                    ) : null}
                  </div>
                  <h3 className="mt-4 text-[17px] font-semibold text-[color:var(--color-ink-950)] md:text-lg">
                    {s.title}
                  </h3>
                  <p className="mt-2 text-[14px] leading-relaxed text-[color:var(--color-ink-600)] md:text-[15px]">
                    {s.body}
                  </p>
                </li>
              )
            })}
          </ol>
        </div>
      </div>
    </section>
  )
}
