export function Footer() {
  return (
    <footer className="border-t border-[color:var(--color-ink-100)] bg-white">
      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 md:grid md:grid-cols-3 md:gap-10 md:px-8 md:py-14">
        <div className="md:col-span-1">
          <div className="flex items-center gap-2">
            <span
              className="inline-flex h-8 w-8 items-center justify-center rounded-md bg-[color:var(--color-ink-950)] text-[12px] font-bold tracking-tight text-white"
              aria-hidden
            >
              A·L
            </span>
            <span className="text-sm font-semibold tracking-tight text-[color:var(--color-ink-950)]">
              A-Level 作业助手
            </span>
          </div>
          <p className="mt-3 max-w-xs text-[13px] leading-relaxed text-[color:var(--color-ink-600)]">
            按 CAIE mark scheme 批改 A-Level 作业。5 个国产大模型交叉校验，错题配讲解。
          </p>
        </div>

        <div className="mt-8 grid grid-cols-2 gap-8 md:col-span-2 md:mt-0">
          <div>
            <p className="text-[12px] font-semibold uppercase tracking-[0.14em] text-[color:var(--color-ink-500)]">
              产品
            </p>
            <ul className="mt-3 space-y-2">
              <li>
                <a href="#how-it-works" className="text-[13px] text-[color:var(--color-ink-700)] hover:text-[color:var(--color-ink-950)]">
                  如何使用
                </a>
              </li>
              <li>
                <a href="#faq" className="text-[13px] text-[color:var(--color-ink-700)] hover:text-[color:var(--color-ink-950)]">
                  常见问题
                </a>
              </li>
              <li>
                <a href="mailto:feedback@yourdomain.com" className="text-[13px] text-[color:var(--color-ink-700)] hover:text-[color:var(--color-ink-950)]">
                  反馈
                </a>
              </li>
            </ul>
          </div>
          <div>
            <p className="text-[12px] font-semibold uppercase tracking-[0.14em] text-[color:var(--color-ink-500)]">
              联系
            </p>
            <ul className="mt-3 space-y-2">
              <li>
                <a href="mailto:feedback@yourdomain.com" className="text-[13px] text-[color:var(--color-ink-700)] hover:text-[color:var(--color-ink-950)]">
                  feedback@yourdomain.com
                </a>
              </li>
            </ul>
          </div>
        </div>
      </div>

      <div className="border-t border-[color:var(--color-ink-100)]">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-5 text-[12px] text-[color:var(--color-ink-500)] sm:flex-row sm:items-center sm:justify-between sm:px-6 md:px-8">
          <p>© 2026 A-Level 作业助手</p>
          <p>ICP 备案号：待补充</p>
        </div>
      </div>
    </footer>
  )
}
