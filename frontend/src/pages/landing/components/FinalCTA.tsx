import { useRef } from 'react'
import { useNavigate } from 'react-router'
import { stashPendingUpload } from '../lib/pendingUpload'

export function FinalCTA() {
  const cameraInputRef = useRef<HTMLInputElement>(null)
  const pickerInputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()

  const handleFiles = (files: FileList | null) => {
    if (!files || files.length === 0) return
    stashPendingUpload(files)
    navigate('/')
  }

  return (
    <section className="bg-white py-14 sm:py-16 md:py-20">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 md:px-8">
        <div className="relative overflow-hidden rounded-3xl border border-[color:var(--color-ink-200)] bg-[color:var(--color-ink-950)] px-6 py-10 text-white shadow-[0_20px_60px_-25px_rgba(15,23,42,0.45)] sm:px-10 sm:py-14 md:px-14 md:py-16">
          {/* Soft brand glow — pure CSS decor */}
          <div
            aria-hidden
            className="pointer-events-none absolute -right-20 -top-20 h-72 w-72 rounded-full bg-[color:var(--color-brand)] opacity-20 blur-3xl"
          />
          <div
            aria-hidden
            className="pointer-events-none absolute -bottom-24 -left-20 h-64 w-64 rounded-full bg-[color:var(--color-brand)] opacity-[0.08] blur-3xl"
          />

          <div className="relative max-w-2xl">
            <h2 className="text-[24px] font-semibold leading-tight tracking-tight sm:text-3xl md:text-[40px] md:leading-[1.1]">
              上传第一张作业图
            </h2>
            <p className="mt-3 text-[15px] leading-relaxed text-white/75 md:text-lg">
              免费试用，不用注册。
            </p>

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

            <div className="mt-7 flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-4">
              <button
                type="button"
                onClick={() => cameraInputRef.current?.click()}
                className="flex h-14 w-full items-center justify-center gap-2 rounded-xl bg-[color:var(--color-brand)] px-6 text-[16px] font-semibold text-white shadow-sm transition hover:-translate-y-0.5 hover:bg-[color:var(--color-brand-hover)] hover:shadow-lg active:translate-y-0 sm:w-auto sm:min-w-[220px]"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5">
                  <path d="M23 19a2 2 0 01-2 2H3a2 2 0 01-2-2V8a2 2 0 012-2h4l2-3h6l2 3h4a2 2 0 012 2z" strokeLinecap="round" strokeLinejoin="round" />
                  <circle cx="12" cy="13" r="4" />
                </svg>
                拍照上传
              </button>
              <button
                type="button"
                onClick={() => pickerInputRef.current?.click()}
                className="flex min-h-[44px] w-full items-center justify-center text-[14px] font-medium text-white/80 underline-offset-4 hover:text-white hover:underline sm:w-auto"
              >
                选择相册图片 / PDF
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
