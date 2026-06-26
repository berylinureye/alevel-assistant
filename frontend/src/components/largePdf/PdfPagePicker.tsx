import type { LargePdfPreviewPage } from '../../types'

interface PdfPagePickerProps {
  pages: LargePdfPreviewPage[]
  selectedPages: number[]
  maxSelected: number
  disabled?: boolean
  onTogglePage: (page: number) => void
  onSelectFirstPages: () => void
  onClearSelection: () => void
}

export function PdfPagePicker({
  pages,
  selectedPages,
  maxSelected,
  disabled = false,
  onTogglePage,
  onSelectFirstPages,
  onClearSelection,
}: PdfPagePickerProps) {
  const selected = new Set(selectedPages)
  const atLimit = selectedPages.length >= maxSelected

  return (
    <section className="space-y-4">
      <div className="flex flex-col gap-3 border-b border-slate-100 pb-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-blue-700">页面选择</p>
          <h3 className="mt-1 text-lg font-semibold text-slate-950">选择这次要批改的页面</h3>
          <p className="mt-1 text-sm leading-6 text-slate-500">
            完整 PDF 会保留在会话里。系统会自动选中可处理页面，你只需要按需微调。
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-600">
            已选择 {selectedPages.length}/{maxSelected} 页
          </span>
          <button
            type="button"
            onClick={onSelectFirstPages}
            disabled={disabled}
            className="rounded-md border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-600 transition hover:border-blue-300 hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            恢复默认选择
          </button>
          <button
            type="button"
            onClick={onClearSelection}
            disabled={disabled || selectedPages.length === 0}
            className="rounded-md border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            清空
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
        {pages.map((page) => {
          const isSelected = selected.has(page.page)
          const cannotSelect = disabled || (!isSelected && atLimit)
          return (
            <button
              key={page.page}
              type="button"
              aria-pressed={isSelected}
              disabled={cannotSelect}
              onClick={() => onTogglePage(page.page)}
              className={`group min-w-0 overflow-hidden rounded-lg border bg-white text-left transition ${
                isSelected
                  ? 'border-blue-500 ring-2 ring-blue-100'
                  : 'border-slate-200 hover:border-blue-300 hover:bg-blue-50/30'
              } ${cannotSelect ? 'cursor-not-allowed opacity-60 hover:border-slate-200 hover:bg-white' : ''}`}
            >
              <div className="relative aspect-[3/4] overflow-hidden bg-slate-100">
                <img
                  src={page.thumbnail_b64}
                  alt={`PDF 第 ${page.page} 页预览`}
                  className="h-full w-full object-cover object-top"
                />
                <span
                  className={`absolute left-2 top-2 rounded-md px-2 py-1 text-xs font-semibold shadow-sm ${
                    isSelected ? 'bg-blue-600 text-white' : 'bg-white/90 text-slate-700'
                  }`}
                >
                  第 {page.page} 页
                </span>
              </div>
              <div className="min-h-[4.25rem] px-3 py-2">
                <p className="text-xs font-medium text-slate-700">第 {page.page} 页</p>
                <p className="mt-1 line-clamp-2 text-[11px] leading-4 text-slate-500">
                  {page.ocr_hint || '暂无可读文本预览'}
                </p>
              </div>
            </button>
          )
        })}
      </div>

      {atLimit ? (
        <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-800">
          一次最多批改 {maxSelected} 页。剩下页面可以下一轮继续选择。
        </p>
      ) : null}
    </section>
  )
}
