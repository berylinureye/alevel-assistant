import { useMemo, useState } from 'react'
import type { LargePdfPrepareResponse, UploadIntent } from '../../types'
import { PaperContextCard } from './PaperContextCard'
import { PdfPagePicker } from './PdfPagePicker'

export interface LargePdfAnalyzeContext {
  selectedPages: number[]
  uploadIntent: UploadIntent
  paperCode: string
  questionNumbers: string
}

interface LargePdfModeProps {
  session: LargePdfPrepareResponse
  uploadIntent: UploadIntent
  initialPaperCode: string
  initialQuestionNumbers: string
  maxSelectedPages: number
  disabled?: boolean
  progress?: { current: number; total: number } | null
  onBack: () => void
  onAnalyzeSelectedPages: (context: LargePdfAnalyzeContext) => void
}

function toAnalyzeIntent(uploadIntent: UploadIntent): UploadIntent {
  return uploadIntent === 'past_paper' ? 'full_past_paper_pdf' : uploadIntent
}

function defaultSelectedPages(session: LargePdfPrepareResponse, maxSelectedPages: number): number[] {
  const markedPages = session.preview_pages
    .filter((page) => page.selected_by_default)
    .map((page) => page.page)

  const source = markedPages.length > 0
    ? markedPages
    : session.preview_pages.map((page) => page.page)

  return source.slice(0, maxSelectedPages)
}

export function LargePdfMode({
  session,
  uploadIntent,
  initialPaperCode,
  initialQuestionNumbers,
  maxSelectedPages,
  disabled = false,
  progress,
  onBack,
  onAnalyzeSelectedPages,
}: LargePdfModeProps) {
  const resolution = session.paper_resolution ?? {}
  const [paperCode, setPaperCode] = useState(initialPaperCode || resolution.paper_code || '')
  const [questionNumbers, setQuestionNumbers] = useState(
    initialQuestionNumbers || (resolution.question_numbers ?? []).join(', '),
  )
  const [selectedPages, setSelectedPages] = useState<number[]>(() =>
    defaultSelectedPages(session, maxSelectedPages),
  )

  const sortedSelectedPages = useMemo(
    () => [...selectedPages].sort((a, b) => a - b),
    [selectedPages],
  )
  const analyzeIntent = toAnalyzeIntent((resolution.upload_intent ?? uploadIntent) as UploadIntent)
  const canAnalyze = sortedSelectedPages.length > 0 && !disabled

  const togglePage = (page: number) => {
    setSelectedPages((prev) => {
      if (prev.includes(page)) return prev.filter((p) => p !== page)
      if (prev.length >= maxSelectedPages) return prev
      return [...prev, page].sort((a, b) => a - b)
    })
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!canAnalyze) return
    onAnalyzeSelectedPages({
      selectedPages: sortedSelectedPages,
      uploadIntent: analyzeIntent,
      paperCode: paperCode.trim(),
      questionNumbers: questionNumbers.trim(),
    })
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="w-full min-w-0 space-y-5 rounded-lg border border-slate-200 bg-white/90 p-4 shadow-sm backdrop-blur sm:p-6"
      data-testid="large-pdf-mode"
    >
      <header className="flex flex-col gap-4 border-b border-slate-100 pb-5 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-blue-700">PDF 选页模式</p>
          <h2 className="mt-1 text-xl font-semibold tracking-tight text-slate-950">已读取整套 PDF</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600 [overflow-wrap:anywhere]">
            {session.filename} · 共 {session.page_count} 页。系统已自动选中可处理页面。
          </p>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            完整 PDF 不需要拆成图片；你可以直接开始，也可以取消封面、空白页或无关页面。
          </p>
        </div>
        <div className="flex shrink-0 flex-col gap-2 sm:items-end">
          <button
            type="button"
            onClick={onBack}
            disabled={disabled}
            className="inline-flex h-9 items-center justify-center rounded-md border border-slate-200 bg-white px-3 text-sm font-medium text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            返回重新上传
          </button>
          <button
            type="submit"
            disabled={!canAnalyze}
            className="inline-flex h-9 items-center justify-center rounded-md bg-slate-950 px-3 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300 sm:min-w-[150px]"
          >
            {disabled ? '正在准备…' : sortedSelectedPages.length === 0 ? '请选择页面' : `开始批改 ${sortedSelectedPages.length} 页`}
          </button>
        </div>
      </header>

      <PaperContextCard
        resolution={resolution}
        paperCode={paperCode}
        questionNumbers={questionNumbers}
        disabled={disabled}
        onPaperCodeChange={setPaperCode}
        onQuestionNumbersChange={setQuestionNumbers}
      />

      <PdfPagePicker
        pages={session.preview_pages}
        selectedPages={sortedSelectedPages}
        maxSelected={maxSelectedPages}
        disabled={disabled}
        onTogglePage={togglePage}
        onSelectFirstPages={() =>
          setSelectedPages(defaultSelectedPages(session, maxSelectedPages))
        }
        onClearSelection={() => setSelectedPages([])}
      />

      {progress ? (
        <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3" role="status" aria-live="polite">
          <div className="flex items-center justify-between gap-3">
            <span className="text-sm font-medium text-blue-950">正在准备选中页面…</span>
            <span className="font-mono text-xs font-semibold tabular-nums text-blue-700">
              {progress.current} / {progress.total}
            </span>
          </div>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-blue-100">
            <div
              className="h-full bg-blue-600 transition-[width] duration-300"
              style={{
                width: progress.total > 0 ? `${Math.min(100, (progress.current / progress.total) * 100)}%` : '0%',
              }}
            />
          </div>
        </div>
      ) : null}

      <footer className="flex flex-col gap-3 border-t border-slate-100 pt-5 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-xs leading-5 text-slate-500">
          本次会把选中的 PDF 页面转入现有批改流程；一次最多 {maxSelectedPages} 页。
        </p>
        <button
          type="submit"
          disabled={!canAnalyze}
          className="inline-flex w-full items-center justify-center rounded-md bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300 sm:w-auto sm:min-w-[190px]"
        >
          {disabled ? '正在准备…' : sortedSelectedPages.length === 0 ? '请选择页面' : `开始批改 ${sortedSelectedPages.length} 页`}
        </button>
      </footer>
    </form>
  )
}
