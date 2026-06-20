import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

export function Nav() {
  const [open, setOpen] = useState(false)

  // Lock body scroll when the mobile sheet is open.
  useEffect(() => {
    if (!open) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [open])

  // Close on Escape.
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  return (
    <>
      <header className="sticky top-0 z-40 border-b border-[color:var(--color-ink-200)] bg-white/85 backdrop-blur-md">
        <nav className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4 md:h-16 md:px-8">
          <Link to="/landing" className="flex items-center gap-2" aria-label="A-Level 作业助手">
            <LogoMark />
            <span className="text-[15px] font-semibold tracking-tight text-[color:var(--color-ink-950)] md:text-base">
              A-Level 作业助手
            </span>
          </Link>

          {/* Desktop menu */}
          <div className="hidden items-center gap-8 md:flex">
            <a
              href="#how-it-works"
              className="text-sm font-medium text-[color:var(--color-ink-700)] transition hover:text-[color:var(--color-ink-950)]"
            >
              如何使用
            </a>
            <a
              href="#faq"
              className="text-sm font-medium text-[color:var(--color-ink-700)] transition hover:text-[color:var(--color-ink-950)]"
            >
              常见问题
            </a>
            <Link
              to="/"
              className="rounded-md border border-[color:var(--color-ink-200)] bg-white px-4 py-2 text-sm font-medium text-[color:var(--color-ink-900)] shadow-sm transition hover:border-[color:var(--color-ink-300)] hover:shadow"
            >
              登录
            </Link>
          </div>

          {/* Mobile: login button + hamburger */}
          <div className="flex items-center gap-2 md:hidden">
            <Link
              to="/"
              className="rounded-md border border-[color:var(--color-ink-200)] bg-white px-3 py-2 text-sm font-medium text-[color:var(--color-ink-900)]"
            >
              登录
            </Link>
            <button
              type="button"
              onClick={() => setOpen(true)}
              aria-label="打开菜单"
              className="flex h-10 w-10 items-center justify-center rounded-md border border-[color:var(--color-ink-200)] bg-white text-[color:var(--color-ink-900)]"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5">
                <line x1="3" y1="6" x2="21" y2="6" strokeLinecap="round" />
                <line x1="3" y1="12" x2="21" y2="12" strokeLinecap="round" />
                <line x1="3" y1="18" x2="21" y2="18" strokeLinecap="round" />
              </svg>
            </button>
          </div>
        </nav>
      </header>

      {/* Mobile sheet */}
      {open ? (
        <div
          className="fixed inset-0 z-50 md:hidden"
          role="dialog"
          aria-modal="true"
          aria-label="主菜单"
        >
          <div
            className="absolute inset-0 bg-black/40"
            onClick={() => setOpen(false)}
          />
          <div className="absolute right-0 top-0 flex h-full w-[82%] max-w-sm flex-col bg-white shadow-xl">
            <div className="flex h-14 items-center justify-between border-b border-[color:var(--color-ink-200)] px-4">
              <span className="text-sm font-semibold text-[color:var(--color-ink-950)]">菜单</span>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="关闭菜单"
                className="flex h-10 w-10 items-center justify-center rounded-md text-[color:var(--color-ink-700)]"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5">
                  <line x1="6" y1="6" x2="18" y2="18" strokeLinecap="round" />
                  <line x1="18" y1="6" x2="6" y2="18" strokeLinecap="round" />
                </svg>
              </button>
            </div>
            <nav className="flex flex-col gap-1 p-3">
              <a
                href="#how-it-works"
                onClick={() => setOpen(false)}
                className="flex min-h-[48px] items-center rounded-md px-3 text-[15px] font-medium text-[color:var(--color-ink-800)] hover:bg-[color:var(--color-ink-100)]"
              >
                如何使用
              </a>
              <a
                href="#faq"
                onClick={() => setOpen(false)}
                className="flex min-h-[48px] items-center rounded-md px-3 text-[15px] font-medium text-[color:var(--color-ink-800)] hover:bg-[color:var(--color-ink-100)]"
              >
                常见问题
              </a>
              <Link
                to="/"
                onClick={() => setOpen(false)}
                className="mt-2 flex min-h-[48px] items-center justify-center rounded-md border border-[color:var(--color-ink-200)] bg-white px-3 text-[15px] font-medium text-[color:var(--color-ink-900)]"
              >
                登录
              </Link>
            </nav>
          </div>
        </div>
      ) : null}
    </>
  )
}

function LogoMark() {
  return (
    <span
      className="inline-flex h-8 w-8 items-center justify-center rounded-md bg-[color:var(--color-ink-950)] text-[12px] font-bold tracking-tight text-white"
      aria-hidden
    >
      A·L
    </span>
  )
}
