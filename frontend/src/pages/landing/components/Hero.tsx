import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { stashPendingUpload } from '../lib/pendingUpload'

/**
 * Hero — emphasizes the equal triad: 批改 · 讲解 · 追问.
 * The chat card previews the 追问 flow (stickiest value prop), with a subtle
 * "5 AI 已交叉校对" stamp that folds in the accuracy message without stealing
 * focus from the conversation.
 */
export function Hero() {
  const cameraInputRef = useRef<HTMLInputElement>(null)
  const pickerInputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()

  const handleFiles = (files: FileList | null) => {
    if (!files || files.length === 0) return
    stashPendingUpload(files)
    navigate('/')
  }

  const triggerCamera = () => cameraInputRef.current?.click()

  return (
    <section className="relative overflow-hidden bg-white">
      {/* Ambient gradient blob — subtle, mobile-first */}
      <div aria-hidden className="pointer-events-none absolute inset-x-0 top-0 h-[340px] bg-gradient-to-b from-[color:var(--color-brand-soft)]/70 via-white to-white" />

      <div className="relative mx-auto max-w-6xl px-4 pt-6 pb-10 sm:px-6 sm:pt-10 sm:pb-14 md:grid md:grid-cols-12 md:gap-10 md:px-8 md:pt-16 md:pb-24">
        {/* Text column */}
        <div className="md:col-span-7 md:pt-4">
          <p className="mb-3 inline-flex items-center gap-2 rounded-full border border-[color:var(--color-ink-200)] bg-white/80 px-3 py-1 text-[12px] font-medium text-[color:var(--color-ink-700)] shadow-sm backdrop-blur">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-500" />
            CAIE A-Level · 5 AI 交叉判分
          </p>

          <h1 className="text-[30px] font-semibold leading-[1.12] tracking-tight text-[color:var(--color-ink-950)] sm:text-4xl md:text-[52px] md:leading-[1.03]">
            拍张作业
            <br className="sm:hidden" />
            <span className="sm:ml-2">AI 老师全包</span>
          </h1>

          {/* Triad — equal pillars */}
          <div className="mt-4 grid grid-cols-3 gap-2 sm:max-w-xl md:mt-5 md:gap-3">
            <PillarChip label="批改" hint="5 AI 交叉" accent="emerald" icon={<CheckIcon />} />
            <PillarChip label="讲解" hint="多种解法" accent="sky" icon={<BookIcon />} />
            <PillarChip label="追问" hint="像真老师" accent="violet" icon={<ChatIcon />} />
          </div>

          <p className="mt-4 max-w-xl text-[14px] leading-relaxed text-[color:var(--color-ink-600)] sm:text-[15px] md:mt-5 md:text-lg">
            5 个 AI 老师一起看卷，每一步对错按 CAIE mark scheme 给分。错题自动配讲解，
            <span className="font-medium text-[color:var(--color-ink-900)]">不懂直接追问</span>，
            换种思路也能讲。
          </p>

          {/* CTA */}
          <div className="mt-5 md:mt-8">
            <input
              ref={cameraInputRef}
              type="file"
              accept="image/*"
              capture="environment"
              multiple
              className="sr-only"
              onChange={(e) => {
                handleFiles(e.target.files)
                e.target.value = ''
              }}
            />
            <input
              ref={pickerInputRef}
              type="file"
              accept="image/*,.pdf,application/pdf"
              multiple
              className="sr-only"
              onChange={(e) => {
                handleFiles(e.target.files)
                e.target.value = ''
              }}
            />

            <button
              type="button"
              onClick={triggerCamera}
              className="group relative flex h-14 w-full items-center justify-center gap-2 overflow-hidden rounded-xl bg-[color:var(--color-brand)] px-6 text-[16px] font-semibold text-white shadow-sm transition hover:-translate-y-0.5 hover:bg-[color:var(--color-brand-hover)] hover:shadow-md active:translate-y-0 md:inline-flex md:h-14 md:w-auto md:min-w-[260px]"
            >
              <span aria-hidden className="pointer-events-none absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/25 to-transparent transition-transform duration-700 ease-out group-hover:translate-x-full" />
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="relative h-5 w-5">
                <path d="M23 19a2 2 0 01-2 2H3a2 2 0 01-2-2V8a2 2 0 012-2h4l2-3h6l2 3h4a2 2 0 012 2z" strokeLinecap="round" strokeLinejoin="round" />
                <circle cx="12" cy="13" r="4" />
              </svg>
              <span className="relative">拍照上传作业</span>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" className="relative h-4 w-4 transition-transform group-hover:translate-x-1">
                <line x1="5" y1="12" x2="19" y2="12" strokeLinecap="round" />
                <polyline points="12 5 19 12 12 19" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>

            <button
              type="button"
              onClick={() => pickerInputRef.current?.click()}
              className="mt-3 flex min-h-[44px] w-full items-center justify-center text-[14px] font-medium text-[color:var(--color-ink-700)] underline-offset-4 hover:underline md:w-auto md:justify-start"
            >
              选择相册图片 / PDF
            </button>
          </div>

          {/* Trust marks */}
          <ul className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-[12.5px] text-[color:var(--color-ink-600)] md:mt-6 md:text-[13px]">
            <li className="inline-flex items-center gap-1.5">
              <CheckDot /> 免费试用
            </li>
            <li className="inline-flex items-center gap-1.5">
              <CheckDot /> 无需注册
            </li>
            <li className="inline-flex items-center gap-1.5">
              <CheckDot /> 30 秒出结果
            </li>
          </ul>
        </div>

        {/* Visual column */}
        <div className="relative mt-8 md:col-span-5 md:mt-0">
          <HeroVisual onClick={triggerCamera} />
        </div>
      </div>
    </section>
  )
}

function PillarChip({
  label,
  hint,
  accent,
  icon,
}: {
  label: string
  hint: string
  accent: 'emerald' | 'sky' | 'violet'
  icon: React.ReactNode
}) {
  const ringClass =
    accent === 'emerald'
      ? 'ring-emerald-200 bg-emerald-50 text-emerald-700'
      : accent === 'sky'
        ? 'ring-sky-200 bg-sky-50 text-sky-700'
        : 'ring-violet-200 bg-violet-50 text-violet-700'
  return (
    <div className={`flex flex-col items-center justify-center rounded-xl px-2 py-2.5 ring-1 ${ringClass}`}>
      <div className="flex items-center gap-1.5">
        <span className="inline-flex h-4 w-4 shrink-0 items-center justify-center">{icon}</span>
        <span className="text-[14px] font-semibold leading-none sm:text-[15px]">{label}</span>
      </div>
      <span className="mt-1 text-[11px] leading-none text-[color:var(--color-ink-600)] sm:text-[12px]">{hint}</span>
    </div>
  )
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" className="h-3.5 w-3.5">
      <path fillRule="evenodd" d="M16.704 5.29a1 1 0 010 1.42l-7.5 7.5a1 1 0 01-1.42 0l-3.5-3.5a1 1 0 011.42-1.42L8.5 12.08l6.79-6.79a1 1 0 011.414 0z" clipRule="evenodd" />
    </svg>
  )
}

function BookIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3.5 w-3.5">
      <path d="M4 4.5A2.5 2.5 0 016.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15z" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M4 19.5A2.5 2.5 0 016.5 17H20" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function ChatIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3.5 w-3.5">
      <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function CheckDot() {
  return (
    <span
      className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-emerald-50 text-emerald-600"
      aria-hidden
    >
      <svg viewBox="0 0 20 20" fill="currentColor" className="h-3 w-3">
        <path
          fillRule="evenodd"
          d="M16.704 5.29a1 1 0 010 1.42l-7.5 7.5a1 1 0 01-1.42 0l-3.5-3.5a1 1 0 011.42-1.42L8.5 12.08l6.79-6.79a1 1 0 011.414 0z"
          clipRule="evenodd"
        />
      </svg>
    </span>
  )
}

/**
 * Visual hero — a live-feel AI conversation preview with typing animation
 * and a "5 AI 已交叉校对" stamp at the top. Designed to telegraph all three
 * pillars (批改 / 讲解 / 追问) within a single card.
 */
function HeroVisual({ onClick }: { onClick: () => void }) {
  // Cycle the "AI is typing..." animation so the card feels alive on scroll-in.
  const [dots, setDots] = useState(1)
  useEffect(() => {
    const id = setInterval(() => setDots((d) => (d % 3) + 1), 450)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="group/card relative mx-auto w-full max-w-md md:max-w-none">
      {/* Hover hint */}
      <div
        aria-hidden
        className="pointer-events-none absolute -top-3 left-1/2 z-20 hidden -translate-x-1/2 rounded-full bg-[color:var(--color-ink-950)] px-3 py-1 text-[11px] font-medium text-white opacity-0 shadow-md transition-opacity duration-200 md:block md:group-hover/card:opacity-100"
      >
        点击试用 →
      </div>

      <button
        type="button"
        onClick={onClick}
        aria-label="点击开始体验 — 上传一张作业图"
        className="relative block w-full cursor-pointer rounded-2xl border border-[color:var(--color-ink-200)] bg-white p-4 text-left shadow-[0_10px_40px_-15px_rgba(15,23,42,0.25)] transition duration-300 hover:-translate-y-1 hover:border-[color:var(--color-brand)] hover:shadow-[0_20px_50px_-15px_rgba(37,99,235,0.25)] sm:p-5"
      >
        {/* Header with accuracy stamp */}
        <div className="flex items-center justify-between border-b border-[color:var(--color-ink-100)] pb-3">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[color:var(--color-brand-soft)] text-[color:var(--color-brand)]">
              <ChatIcon />
            </span>
            <div>
              <p className="text-[12.5px] font-semibold text-[color:var(--color-ink-900)]">AI 老师 · 可追问</p>
              <p className="text-[10.5px] uppercase tracking-wide text-[color:var(--color-ink-500)]">
                CAIE 9709 · logarithms
              </p>
            </div>
          </div>
          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 ring-1 ring-emerald-200">
            <svg viewBox="0 0 20 20" fill="currentColor" className="h-2.5 w-2.5">
              <path fillRule="evenodd" d="M16.704 5.29a1 1 0 010 1.42l-7.5 7.5a1 1 0 01-1.42 0l-3.5-3.5a1 1 0 011.42-1.42L8.5 12.08l6.79-6.79a1 1 0 011.414 0z" clipRule="evenodd" />
            </svg>
            5 AI 已校对
          </span>
        </div>

        {/* Grade strip — the "批改" pillar in action */}
        <div className="mt-3 flex items-center gap-2 rounded-lg bg-[color:var(--color-ink-50)]/70 px-2.5 py-1.5 text-[11px]">
          <span className="inline-flex rounded bg-white px-1.5 py-0.5 font-mono text-[10px] font-semibold text-[color:var(--color-ink-800)] ring-1 ring-[color:var(--color-ink-200)]">
            3/5
          </span>
          <span className="text-[color:var(--color-ink-600)]">M1 ✓ · A1 漏一个解 · B1 未写 x &gt; 0</span>
        </div>

        {/* Chat rows — student question + AI answer with multi-path hint */}
        <div className="mt-3 space-y-2.5">
          <div className="flex justify-end">
            <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-[color:var(--color-ink-100)] px-3 py-2 text-[12.5px] leading-relaxed text-[color:var(--color-ink-800)]">
              这题为什么要先设 k = log₂x？
            </div>
          </div>

          <div className="flex items-start gap-2">
            <span className="mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[color:var(--color-ink-950)] text-[10px] font-semibold text-white">
              AI
            </span>
            <div className="max-w-[85%] rounded-2xl rounded-tl-sm border border-[color:var(--color-ink-100)] bg-white px-3 py-2 text-[12.5px] leading-relaxed text-[color:var(--color-ink-800)]">
              这是 log 方程的 <span className="font-medium text-[color:var(--color-ink-950)]">标准套路</span>
              ——令 <code className="font-mono">k = log₂x</code>，把指数方程转成 k 的二次方程就能解。
              <div className="mt-2 rounded-md bg-[color:var(--color-brand-soft)] px-2 py-1.5 text-[11.5px] text-[color:var(--color-brand-hover)]">
                ✦ 换个思路：两边同时用 2 为底的指数也行
              </div>
            </div>
          </div>

          {/* Typing indicator — makes it feel live */}
          <div className="flex items-start gap-2">
            <span className="mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[color:var(--color-ink-950)] text-[10px] font-semibold text-white">
              AI
            </span>
            <div className="inline-flex items-center gap-1 rounded-2xl rounded-tl-sm border border-[color:var(--color-ink-100)] bg-white px-3 py-2 text-[12.5px] text-[color:var(--color-ink-400)]">
              <span>正在思考</span>
              <span className="inline-block w-3 font-mono">{'.'.repeat(dots)}</span>
            </div>
          </div>
        </div>

        {/* Follow-up input affordance */}
        <div className="mt-3 flex items-center gap-2 rounded-lg border border-dashed border-[color:var(--color-ink-200)] px-3 py-2">
          <ChatIcon />
          <span className="flex-1 text-[12px] text-[color:var(--color-ink-500)]">继续追问…</span>
          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-[color:var(--color-brand)]">
            发送
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3 w-3">
              <line x1="5" y1="12" x2="19" y2="12" strokeLinecap="round" />
              <polyline points="12 5 19 12 12 19" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
        </div>
      </button>
    </div>
  )
}
