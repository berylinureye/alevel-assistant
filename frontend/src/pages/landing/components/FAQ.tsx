import { useInViewFadeIn } from '../hooks/useInViewFadeIn'

const QA = [
  {
    q: '支持哪些考试局和科目？',
    a: '目前支持 CAIE A-Level：Mathematics (9709)、Further Mathematics (9231)、Physics (9702)。Edexcel 和 AQA 考试局在计划中。',
  },
  {
    q: '批改逻辑是什么？为什么说"按 mark scheme"？',
    a: 'CAIE 的 mark scheme 给分到每个步骤——method mark 看过程，accuracy mark 看结果。系统会拆解学生解答的每一步，对照 mark scheme 给出的给分点，分别判定 M1/M2/A1/B1 等 mark 是否拿到。这是和"只判断最终答案对错"的批改工具最大的区别。',
  },
  {
    q: '为什么要用 5 个模型？',
    a: '单个大语言模型在数学推理上的 hallucination 率不低。我们让 DeepSeek、Qwen-Fast、Qwen-Max、GLM-4-Plus、GLM-5.1 并行批改同一题，通过投票机制决定最终判分。实测误判率比单模型显著降低。',
  },
  {
    q: '手写答案能识别吗？',
    a: '可以。支持中英文手写 + 数学符号识别。页面会显示识别率，如果 OCR 出错可以手动修正后重新批改。',
  },
  {
    q: '我的作业数据安全吗？',
    a: '作业图片仅用于本次批改，不用于训练模型，不分享给第三方。可随时在个人中心删除历史记录。',
  },
  {
    q: '多少钱？',
    a: '目前完全免费，面向早期用户。后续会上线付费方案，早期用户会保留优惠。',
  },
  {
    q: '有小程序吗？',
    a: '小程序开发中。网页版在手机浏览器里打开体验也不错。',
  },
  {
    q: '发现批改错误怎么办？',
    a: '每道题下方都有反馈按钮。反馈的题目会被人工复核，用来持续优化批改逻辑。',
  },
]

export function FAQ() {
  const { ref, inView } = useInViewFadeIn<HTMLDivElement>()
  return (
    <section
      id="faq"
      className="border-t border-[color:var(--color-ink-100)] bg-white py-16 sm:py-20 md:py-24"
    >
      <div className="mx-auto max-w-[800px] px-4 sm:px-6 md:px-8">
        <header className="mb-8 md:mb-10">
          <p className="text-[12px] font-semibold uppercase tracking-[0.14em] text-[color:var(--color-ink-500)]">
            FAQ
          </p>
          <h2 className="mt-2 text-[24px] font-semibold tracking-tight text-[color:var(--color-ink-950)] sm:text-3xl md:text-4xl">
            常见问题
          </h2>
        </header>

        <div ref={ref} className={`lp-reveal ${inView ? 'lp-in' : ''} divide-y divide-[color:var(--color-ink-100)] border-y border-[color:var(--color-ink-100)]`}>
          {QA.map((item, i) => (
            <details
              key={i}
              className="group py-4 [&_summary]:list-none [&_summary::-webkit-details-marker]:hidden"
            >
              <summary className="flex min-h-[48px] cursor-pointer items-center justify-between gap-4 text-[15px] font-medium text-[color:var(--color-ink-900)] transition hover:text-[color:var(--color-brand)] md:text-base">
                <span className="flex items-start gap-3">
                  <span className="mt-0.5 font-mono text-[12px] font-semibold text-[color:var(--color-ink-400)]">
                    Q{String(i + 1).padStart(2, '0')}
                  </span>
                  <span>{item.q}</span>
                </span>
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[color:var(--color-ink-100)] text-[color:var(--color-ink-600)] transition group-open:rotate-45 group-open:bg-[color:var(--color-ink-950)] group-open:text-white">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3.5 w-3.5">
                    <line x1="12" y1="5" x2="12" y2="19" strokeLinecap="round" />
                    <line x1="5" y1="12" x2="19" y2="12" strokeLinecap="round" />
                  </svg>
                </span>
              </summary>
              <div className="mt-3 pl-9 pr-2 text-[14px] leading-relaxed text-[color:var(--color-ink-600)] md:text-[15px]">
                {item.a}
              </div>
            </details>
          ))}
        </div>
      </div>
    </section>
  )
}
