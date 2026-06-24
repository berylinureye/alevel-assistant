import { useEffect, useMemo, useRef, useState } from 'react'
import type { AnalyzeRequest, LargePdfPrepareResponse, UploadIntent } from '../types'
import { getPdfPageCount, pdfPagesToImages, pdfToImages } from '../utils/pdfToImages'
import { prepareUpload, trackEvent } from '../api/client'
import { prepareLargePdf } from '../api/largePdfClient'
import { ImageCropper } from './ImageCropper'
import { LargePdfMode, type LargePdfAnalyzeContext } from './largePdf/LargePdfMode'

type PrepareStatus = 'processing' | 'ready' | 'failed'

interface PrepareState {
  status: PrepareStatus
  uploadId?: string
}

// Must match MAX_PAGES_PER_REQUEST in api/routes.py. Uploading more than this
// yields "Max N pages per request." and the analyze request fails entirely.
// Keep both ends in lockstep.
const MAX_FILES = 24
const MAX_BYTES = 20 * 1024 * 1024
// PDF file size cap is larger than single-image cap because a single PDF can
// legitimately contain up to MAX_FILES pages worth of scans.
const MAX_SMALL_PDF_BYTES = 40 * 1024 * 1024
const MAX_LARGE_PDF_BYTES = 80 * 1024 * 1024
const ALLOWED_TYPES = new Set([
  'image/jpeg',
  'image/png',
  'image/webp',
  'image/heic',
  'image/heif',
])

const INTENT_OPTIONS: Array<{
  value: UploadIntent
  title: string
  description: string
}> = [
  {
    value: 'unknown',
    title: '不确定，帮我识别',
    description: '默认路径：系统先判断是否是真题，再选择批改方式',
  },
  {
    value: 'past_paper',
    title: 'Past Paper / 真题卷',
    description: '可填写 paper code，优先匹配本地 mark scheme',
  },
  {
    value: 'custom_homework',
    title: '老师布置的作业',
    description: '不强行匹配真题，直接走开放 AI 批改',
  },
  {
    value: 'answer_pages_only',
    title: '只有答案页',
    description: '系统会提示补充题目页或 paper code',
  },
]

const RESULT_EXPECTATIONS = [
  '每题得分',
  '错因定位',
  '关键步骤反馈',
  '薄弱知识点',
  '下一组练习建议',
]

function isAllowedType(file: File): boolean {
  if (ALLOWED_TYPES.has(file.type)) return true
  // iOS Safari 有时 file.type 为空或为通用 image/*，放宽为只要是图片类就接受
  if (file.type.startsWith('image/')) return true
  const name = file.name.toLowerCase()
  if (/\.(jpe?g|png|webp|heic|heif|gif|bmp|tiff?)$/.test(name)) return true
  // 兜底：iPhone 相册有时文件名无后缀（例如 "image"），但 type 为 image/*，已在上面判过
  // 若 type 也为空、名字也没扩展名，这里仍拒绝
  return false
}

function processIncomingFiles(incoming: File[], existing: File[]): { next: File[]; messages: string[] } {
  const messages: string[] = []
  const room = MAX_FILES - existing.length
  if (room <= 0) {
    messages.push(`已达到 ${MAX_FILES} 张上限，未添加更多图片`)
    return { next: existing, messages }
  }

  let skippedFormat = 0
  let skippedSize = 0
  const accepted: File[] = []

  for (const f of incoming) {
    if (!isAllowedType(f)) {
      skippedFormat++
      continue
    }
    if (f.size > MAX_BYTES) {
      skippedSize++
      continue
    }
    accepted.push(f)
  }

  if (skippedFormat > 0) {
    messages.push(`已跳过 ${skippedFormat} 张：格式须为 JPG / PNG / WebP / HEIC`)
  }
  if (skippedSize > 0) {
    messages.push(`已跳过 ${skippedSize} 张：单张超过 20 MB`)
  }

  let toAdd = accepted
  if (accepted.length > room) {
    toAdd = accepted.slice(0, room)
    messages.push(`一次最多 ${MAX_FILES} 张，已截断多余 ${accepted.length - room} 张`)
  }

  return { next: [...existing, ...toAdd], messages }
}

export interface UploadFormProps {
  onSubmit: (req: AnalyzeRequest) => void
  loading: boolean
  onResetUpload?: () => void
  onCancelAnalysis?: () => void
  /** Files handed off from the landing page — auto-loaded once on mount. */
  initialFiles?: File[] | null
  /** Called once initialFiles have been accepted into local state. */
  onInitialFilesConsumed?: () => void
}

function FilePreviewTile({
  file,
  previewUrl,
  removable,
  onRemove,
  onEdit,
}: {
  file: File
  previewUrl: string
  removable: boolean
  onRemove: () => void
  onEdit?: () => void
}) {
  const [previewFailed, setPreviewFailed] = useState(false)
  const ext = file.name.split('.').pop()?.toUpperCase() ?? 'FILE'

  return (
    <div className="group relative h-24 w-24 shrink-0 overflow-hidden rounded-md border border-slate-200 bg-slate-100 shadow-sm transition hover:z-10 hover:-translate-y-0.5 hover:shadow-md">
      {!previewFailed ? (
        <img
          src={previewUrl}
          alt=""
          title={file.name}
          className="h-full w-full object-cover"
          onError={() => setPreviewFailed(true)}
        />
      ) : (
        <div
          title={file.name}
          className="flex h-full w-full flex-col items-center justify-center bg-slate-100 px-2 text-center"
        >
          <span className="text-xs font-semibold text-slate-700">{ext}</span>
          <span className="mt-1 line-clamp-2 text-[10px] text-slate-500">预览不可用，仍可上传</span>
        </div>
      )}
      {onEdit && (
        <button
          type="button"
          onClick={(e) => {
            e.preventDefault()
            if (removable) onEdit()
          }}
          disabled={!removable}
          title="裁剪"
          className="absolute left-1 top-1 flex h-6 w-6 items-center justify-center rounded-full bg-gray-600/85 text-white opacity-100 shadow transition hover:bg-blue-600 md:opacity-0 md:group-hover:opacity-100 disabled:opacity-40"
          aria-label="裁剪此图"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3.5 w-3.5">
            <path d="M6 2v14a2 2 0 002 2h14" />
            <path d="M18 22V8a2 2 0 00-2-2H2" />
          </svg>
        </button>
      )}
      <button
        type="button"
        onClick={(e) => {
          e.preventDefault()
          if (removable) onRemove()
        }}
        disabled={!removable}
        title="移除"
        className="absolute right-1 top-1 flex h-6 w-6 items-center justify-center rounded-full bg-gray-600/85 text-sm leading-none text-white opacity-100 shadow transition hover:bg-red-600 md:opacity-0 md:group-hover:opacity-100 disabled:opacity-40"
        aria-label="移除此图"
      >
        ×
      </button>
    </div>
  )
}

function ImagesPreview({
  files,
  prepareStates,
  onBack,
  onStart,
}: {
  files: File[]
  prepareStates: Map<File, PrepareState>
  onBack: () => void
  onStart: () => void
}) {
  const [index, setIndex] = useState(0)
  const [zoomed, setZoomed] = useState(false)
  const touchStartX = useRef<number | null>(null)

  const urls = useMemo(() => files.map((f) => URL.createObjectURL(f)), [files])

  useEffect(() => {
    return () => {
      for (const x of urls) URL.revokeObjectURL(x)
    }
  }, [urls])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft') {
        setZoomed(false)
        setIndex((i) => Math.max(0, i - 1))
      } else if (e.key === 'ArrowRight') {
        setZoomed(false)
        setIndex((i) => Math.min(files.length - 1, i + 1))
      } else if (e.key === 'Escape') onBack()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [files.length, onBack])

  const onTouchStart = (e: React.TouchEvent) => {
    if (zoomed) return
    touchStartX.current = e.touches[0].clientX
  }
  const onTouchEnd = (e: React.TouchEvent) => {
    if (zoomed || touchStartX.current === null) return
    const dx = e.changedTouches[0].clientX - touchStartX.current
    touchStartX.current = null
    if (Math.abs(dx) < 40) return
    setZoomed(false)
    if (dx < 0) setIndex((i) => Math.min(files.length - 1, i + 1))
    else setIndex((i) => Math.max(0, i - 1))
  }

  const readyCount = files.reduce(
    (n, f) => n + (prepareStates.get(f)?.status === 'ready' ? 1 : 0),
    0,
  )
  const processingCount = files.reduce(
    (n, f) => n + (prepareStates.get(f)?.status === 'processing' ? 1 : 0),
    0,
  )
  const allReady = readyCount === files.length
  const statusText = allReady
    ? '识别完成，可开始批改'
    : processingCount > 0
      ? `识别中… ${readyCount}/${files.length}`
      : `已识别 ${readyCount}/${files.length}`

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-black text-white">
      <header className="flex shrink-0 items-center justify-between gap-2 border-b border-white/10 bg-black/80 px-3 py-2.5 sm:px-4 sm:py-3">
        <button
          type="button"
          onClick={onBack}
          title="返回重新上传"
          className="inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-md border border-white/20 px-2.5 py-1.5 text-[13px] hover:bg-white/10 sm:text-sm"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4">
            <polyline points="15 18 9 12 15 6" />
          </svg>
          <span className="hidden sm:inline">返回重新上传</span>
          <span className="sm:hidden">返回</span>
        </button>
        <div className="min-w-0 flex-1 text-center text-white/90">
          <div className="text-[13px] leading-tight sm:text-sm">
            {index + 1} / {files.length}
          </div>
          <div className="mt-0.5 truncate text-[11px] leading-tight text-white/60 sm:text-xs">
            {statusText}
          </div>
        </div>
        <button
          type="button"
          onClick={onStart}
          disabled={!allReady}
          title={allReady ? '开始批改' : `等待全部 ${files.length} 张识别完成`}
          className="inline-flex shrink-0 items-center whitespace-nowrap rounded-md bg-blue-600 px-3 py-1.5 text-[13px] font-semibold text-white shadow-sm transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:bg-blue-600/40 disabled:hover:bg-blue-600/40 sm:px-4 sm:text-sm"
        >
          {allReady ? '开始批改' : `识别中 ${readyCount}/${files.length}`}
        </button>
      </header>

      <main
        className="relative flex flex-1 items-center justify-center overflow-hidden"
        onTouchStart={onTouchStart}
        onTouchEnd={onTouchEnd}
      >
        {index > 0 && (
          <button
            type="button"
            onClick={() => {
              setZoomed(false)
              setIndex((i) => Math.max(0, i - 1))
            }}
            aria-label="上一张"
            className="absolute left-2 top-1/2 z-10 hidden h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full bg-white/10 text-white backdrop-blur hover:bg-white/20 sm:flex"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5">
              <polyline points="15 18 9 12 15 6" />
            </svg>
          </button>
        )}
        {index < files.length - 1 && (
          <button
            type="button"
            onClick={() => {
              setZoomed(false)
              setIndex((i) => Math.min(files.length - 1, i + 1))
            }}
            aria-label="下一张"
            className="absolute right-2 top-1/2 z-10 hidden h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full bg-white/10 text-white backdrop-blur hover:bg-white/20 sm:flex"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5">
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </button>
        )}

        <div
          className={`h-full w-full ${zoomed ? 'overflow-auto' : 'flex items-center justify-center'}`}
        >
          <img
            src={urls[index]}
            alt=""
            onClick={() => setZoomed((z) => !z)}
            className={
              zoomed
                ? 'max-w-none cursor-zoom-out'
                : 'max-h-full max-w-full cursor-zoom-in object-contain'
            }
          />
        </div>
      </main>

      {files.length > 1 && (
        <footer className="shrink-0 border-t border-white/10 bg-black/80 px-4 py-2">
          <div className="flex flex-wrap items-center justify-center gap-1.5">
            {files.map((f, i) => {
              const s = prepareStates.get(f)?.status
              const dotClass =
                s === 'ready'
                  ? 'bg-emerald-400'
                  : s === 'failed'
                    ? 'bg-red-400'
                    : s === 'processing'
                      ? 'bg-blue-400 animate-pulse'
                      : 'bg-white/30'
              return (
                <button
                  key={i}
                  type="button"
                  onClick={() => {
                    setZoomed(false)
                    setIndex(i)
                  }}
                  aria-label={`第 ${i + 1} 张`}
                  className={`h-2 w-6 rounded-full transition ${dotClass} ${
                    i === index ? 'opacity-100 ring-1 ring-white/70' : 'opacity-70'
                  }`}
                />
              )
            })}
          </div>
        </footer>
      )}
    </div>
  )
}

export function UploadForm({
  onSubmit,
  loading,
  onResetUpload,
  onCancelAnalysis,
  initialFiles,
  onInitialFilesConsumed,
}: UploadFormProps) {
  const [files, setFiles] = useState<File[]>([])
  const [prepareStates, setPrepareStates] = useState<Map<File, PrepareState>>(new Map())
  const [batchMessages, setBatchMessages] = useState<string[]>([])
  const [isDragOver, setIsDragOver] = useState(false)
  const [pdfLoading, setPdfLoading] = useState(false)
  const [pdfProgress, setPdfProgress] = useState<{ current: number; total: number } | null>(null)
  const [largePdfSession, setLargePdfSession] = useState<LargePdfPrepareResponse | null>(null)
  const [largePdfFile, setLargePdfFile] = useState<File | null>(null)
  const [pendingCropUrl, setPendingCropUrl] = useState<string | null>(null)
  const [editingIndex, setEditingIndex] = useState<number | null>(null)
  const [showPreview, setShowPreview] = useState(false)
  const [uploadIntent, setUploadIntent] = useState<UploadIntent>('unknown')
  const [paperCode, setPaperCode] = useState('')
  const [questionNumbers, setQuestionNumbers] = useState('')
  const filesRef = useRef<File[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)
  const cameraInputRef = useRef<HTMLInputElement>(null)
  const pdfInputRef = useRef<HTMLInputElement>(null)
  const mobileCombinedInputRef = useRef<HTMLInputElement>(null)
  const dragDepthRef = useRef(0)

  const previewUrls = useMemo(() => files.map((f) => URL.createObjectURL(f)), [files])

  useEffect(() => {
    return () => {
      for (const u of previewUrls) {
        URL.revokeObjectURL(u)
      }
    }
  }, [previewUrls])

  useEffect(() => {
    if (batchMessages.length === 0) return
    const t = window.setTimeout(() => setBatchMessages([]), 6000)
    return () => clearTimeout(t)
  }, [batchMessages])

  // Clean up pending crop URL on unmount
  useEffect(() => {
    return () => {
      if (pendingCropUrl) URL.revokeObjectURL(pendingCropUrl)
    }
  }, [pendingCropUrl])

  useEffect(() => {
    filesRef.current = files
  }, [files])

  // Consume files handed off from the landing page exactly once.
  const initialFilesConsumedRef = useRef(false)
  useEffect(() => {
    if (initialFilesConsumedRef.current) return
    if (!initialFiles || initialFiles.length === 0) return
    initialFilesConsumedRef.current = true
    addFilesFromList(initialFiles)
    onInitialFilesConsumed?.()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialFiles])

  const atCapacity = files.length >= MAX_FILES
  const canAddMore = !atCapacity && !loading && !pdfLoading && !largePdfSession

  const kickoffPrepare = (file: File) => {
    setPrepareStates((prev) => {
      const next = new Map(prev)
      next.set(file, { status: 'processing' })
      return next
    })
    prepareUpload(file)
      .then((res) => {
        setPrepareStates((prev) => {
          const next = new Map(prev)
          next.set(file, { status: 'ready', uploadId: res.upload_id })
          return next
        })
      })
      .catch((err: unknown) => {
        const message = err instanceof Error ? err.message : '未知错误'
        setPrepareStates((prev) => {
          const next = new Map(prev)
          next.set(file, { status: 'failed' })
          return next
        })
        setBatchMessages((prev) => [
          ...prev,
          `${file.name || '未命名图片'} 预识别失败：${message}`,
        ])
      })
  }

  const addFilesFromList = (list: FileList | File[] | null) => {
    if (!list || list.length === 0) return
    const incoming = Array.from(list)
    const current = filesRef.current
    const { next, messages } = processIncomingFiles(incoming, current)
    const added = next.slice(current.length)
    if (added.length === 0 && messages.length === 0) return
    setFiles(next)
    filesRef.current = next
    if (messages.length > 0) setBatchMessages(messages)
    for (const f of added) kickoffPrepare(f)
  }

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    addFilesFromList(e.target.files)
    e.target.value = ''
  }

  const handleRemoveAt = (index: number) => {
    setFiles((prev) => {
      const removed = prev[index]
      if (removed) {
        setPrepareStates((s) => {
          const next = new Map(s)
          next.delete(removed)
          return next
        })
      }
      return prev.filter((_, i) => i !== index)
    })
  }

  const openFilePicker = () => {
    if (!canAddMore) return
    fileInputRef.current?.click()
  }

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (!canAddMore) return
    dragDepthRef.current += 1
    if (dragDepthRef.current === 1) setIsDragOver(true)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    dragDepthRef.current -= 1
    if (dragDepthRef.current <= 0) {
      dragDepthRef.current = 0
      setIsDragOver(false)
    }
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    dragDepthRef.current = 0
    setIsDragOver(false)
    if (!canAddMore) return
    addFilesFromList(e.dataTransfer.files)
  }

  /* ---- Camera: capture → add directly (crop is now optional per-tile) ---- */
  const handleCameraCapture = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    e.target.value = ''
    if (!f) return
    addFilesFromList([f])
  }

  const handleStartCrop = (index: number) => {
    const f = filesRef.current[index]
    if (!f || loading) return
    if (pendingCropUrl) URL.revokeObjectURL(pendingCropUrl)
    setPendingCropUrl(URL.createObjectURL(f))
    setEditingIndex(index)
  }

  const handleCropConfirm = (croppedFile: File) => {
    if (pendingCropUrl) URL.revokeObjectURL(pendingCropUrl)
    setPendingCropUrl(null)
    if (editingIndex !== null) {
      const idx = editingIndex
      const oldFile = filesRef.current[idx]
      setEditingIndex(null)
      const next = filesRef.current.map((f, i) => (i === idx ? croppedFile : f))
      setFiles(next)
      filesRef.current = next
      if (oldFile) {
        setPrepareStates((s) => {
          const nxt = new Map(s)
          nxt.delete(oldFile)
          return nxt
        })
      }
      kickoffPrepare(croppedFile)
    } else {
      addFilesFromList([croppedFile])
    }
  }

  const handleCropCancel = () => {
    if (pendingCropUrl) URL.revokeObjectURL(pendingCropUrl)
    setPendingCropUrl(null)
    setEditingIndex(null)
  }

  /* ---- Open preview: kick off prepareUpload for any file without a cached upload_id ---- */
  const openPreview = () => {
    if (files.length === 0 || loading || pdfLoading) return
    for (const f of files) {
      const st = prepareStates.get(f)
      if (!st || st.status === 'failed') {
        kickoffPrepare(f)
      }
    }
    setShowPreview(true)
  }

  const handlePreviewStart = () => {
    setShowPreview(false)
    const upload_ids = files.map((f) => {
      const s = prepareStates.get(f)
      return s?.status === 'ready' ? s.uploadId ?? null : null
    })
    trackEvent('ui_upload_submit', {
      page_count: files.length,
      total_bytes: files.reduce((a, f) => a + f.size, 0),
      prepared_count: upload_ids.filter(Boolean).length,
      upload_intent: uploadIntent,
      has_paper_code: paperCode.trim().length > 0,
      has_question_numbers: questionNumbers.trim().length > 0,
    })
    onSubmit({
      images: files,
      upload_ids,
      upload_intent: uploadIntent,
      paper_code: paperCode.trim(),
      question_numbers: questionNumbers.trim(),
    })
  }

  /* ---- Mobile combined picker (image or pdf via native sheet) ---- */
  const handleMobileCombinedSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(e.target.files ?? [])
    e.target.value = ''
    if (selected.length === 0) return
    const images: File[] = []
    let pdf: File | null = null
    for (const f of selected) {
      const isPdf = f.type === 'application/pdf' || /\.pdf$/i.test(f.name)
      if (isPdf && !pdf) pdf = f
      else if (!isPdf) images.push(f)
    }
    if (images.length > 0) {
      addFilesFromList(images)
    }
    if (pdf) await processPdfFile(pdf)
  }

  /**
   * Convert a PDF into page images, adding each page to the form immediately
   * as it is rendered so that prepare-upload (OCR + segmentation on the
   * server) starts in parallel with the remaining render work. This is the
   * difference between "AI thinks for 90 s before starting" (all prepares
   * fire serially AFTER conversion) and "AI starts within a few seconds"
   * (prepares already ~done by the time the last page finishes rendering).
   */
  const processPdfFile = async (file: File) => {
    if (file.size > MAX_LARGE_PDF_BYTES) {
      setBatchMessages([`PDF 文件超过 ${MAX_LARGE_PDF_BYTES / 1024 / 1024} MB，请压缩后重试`])
      return
    }
    setPdfLoading(true)
    setPdfProgress({ current: 0, total: 0 })
    try {
      const pageCount = await getPdfPageCount(file)
      const useLargePdfMode =
        uploadIntent === 'past_paper' ||
        pageCount > MAX_FILES ||
        file.size > MAX_SMALL_PDF_BYTES

      if (useLargePdfMode) {
        if (filesRef.current.length > 0) {
          setBatchMessages(['请先清空当前图片，再上传完整 PDF 进入选页模式'])
          return
        }
        const prepared = await prepareLargePdf(file, {
          uploadIntent: uploadIntent === 'past_paper' ? 'full_past_paper_pdf' : uploadIntent,
          paperCode,
          questionNumbers,
        })
        setLargePdfFile(file)
        setLargePdfSession(prepared)
        setBatchMessages([`已读取 ${prepared.page_count} 页 PDF，已自动选中可处理页面`])
        trackEvent('ui_large_pdf_prepare', {
          page_count: prepared.page_count,
          upload_intent: uploadIntent,
          match_confidence: prepared.paper_resolution?.match_confidence,
          has_paper_code: paperCode.trim().length > 0,
        })
        return
      }

      const room = MAX_FILES - filesRef.current.length
      if (room <= 0) {
        setBatchMessages([`已达到 ${MAX_FILES} 张上限，无法添加 PDF 页面`])
        return
      }
      const { files: pageFiles, totalPages, skipped } = await pdfToImages(file, room, {
        onPage: (pageFile) => {
          // Add one file at a time — addFilesFromList kicks off prepare-upload
          // synchronously for new files, so each page starts its server-side
          // OCR immediately after rendering, overlapping the next page's render.
          addFilesFromList([pageFile])
        },
        onProgress: (current, total) => {
          setPdfProgress({ current, total })
        },
      })
      const msgs: string[] = [`已将 PDF 的 ${pageFiles.length} 页转换为图片`]
      if (skipped > 0) {
        msgs.push(`PDF 共 ${totalPages} 页，因上限已跳过后 ${skipped} 页`)
      }
      setBatchMessages(msgs)
    } catch (err) {
      setBatchMessages([err instanceof Error ? err.message : 'PDF 解析失败，请检查文件是否损坏'])
    } finally {
      setPdfLoading(false)
      setPdfProgress(null)
    }
  }

  /* ---- PDF upload (desktop picker) ---- */
  const handlePdfSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    await processPdfFile(file)
  }

  /* ---- Submit: now triggers preview instead of direct analyze ---- */
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    openPreview()
  }

  const canSubmit = files.length > 0 && !loading && !pdfLoading

  const countClass =
    files.length >= MAX_FILES ? 'font-medium text-amber-600' : 'text-slate-600'

  const handleResetUpload = () => {
    if (loading || (files.length === 0 && !largePdfSession)) return
    onResetUpload?.()
    setFiles([])
    setLargePdfSession(null)
    setLargePdfFile(null)
    setPrepareStates(new Map())
    setBatchMessages([])
    window.setTimeout(() => {
      fileInputRef.current?.click()
    }, 0)
  }

  const handleCancel = () => {
    if (!loading) return
    onCancelAnalysis?.()
  }

  const handleLargePdfBack = () => {
    if (loading || pdfLoading) return
    setLargePdfSession(null)
    setLargePdfFile(null)
    setBatchMessages([])
  }

  const handleLargePdfAnalyze = async (context: LargePdfAnalyzeContext) => {
    if (!largePdfFile || loading || pdfLoading) return
    setPdfLoading(true)
    setPdfProgress({ current: 0, total: context.selectedPages.length })
    try {
      const { files: pageFiles } = await pdfPagesToImages(largePdfFile, context.selectedPages, {
        onProgress: (current, total) => setPdfProgress({ current, total }),
      })
      trackEvent('ui_large_pdf_submit', {
        pdf_id: largePdfSession?.pdf_id,
        page_count: largePdfSession?.page_count,
        selected_count: context.selectedPages.length,
        selected_pages: context.selectedPages,
        upload_intent: context.uploadIntent,
        has_paper_code: context.paperCode.trim().length > 0,
        has_question_numbers: context.questionNumbers.trim().length > 0,
      })
      onSubmit({
        images: pageFiles,
        upload_intent: context.uploadIntent,
        paper_code: context.paperCode.trim(),
        question_numbers: context.questionNumbers.trim(),
      })
    } catch (err) {
      setBatchMessages([err instanceof Error ? err.message : 'PDF 页面准备失败，请重新选择页面'])
    } finally {
      setPdfLoading(false)
      setPdfProgress(null)
    }
  }

  const batchMessagesToast = batchMessages.length > 0 ? (
    <div
      className="fixed bottom-4 left-1/2 z-50 max-w-md -translate-x-1/2 rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-white shadow-lg"
      role="status"
    >
      <div className="space-y-1.5">
        {batchMessages.map((msg, idx) => (
          <p key={idx}>{msg}</p>
        ))}
      </div>
    </div>
  ) : null

  if (largePdfSession && largePdfFile) {
    return (
      <>
        <LargePdfMode
          key={largePdfSession.pdf_id}
          session={largePdfSession}
          uploadIntent={uploadIntent}
          initialPaperCode={paperCode}
          initialQuestionNumbers={questionNumbers}
          maxSelectedPages={MAX_FILES}
          disabled={loading || pdfLoading}
          progress={pdfLoading ? pdfProgress : null}
          onBack={handleLargePdfBack}
          onAnalyzeSelectedPages={handleLargePdfAnalyze}
        />
        {batchMessagesToast}
      </>
    )
  }

  return (
    <>
      <form
        onSubmit={handleSubmit}
        className="w-full min-w-0 space-y-6 rounded-lg border border-slate-200 bg-white/90 p-4 shadow-sm backdrop-blur sm:p-6"
      >
        {/* Hidden file inputs */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".jpg,.jpeg,.png,.webp,.heic,.heif,image/jpeg,image/png,image/webp,image/heic,image/heif"
          multiple
          className="sr-only"
          onChange={handleFileInputChange}
          disabled={loading || atCapacity || pdfLoading}
        />
        <input
          ref={pdfInputRef}
          type="file"
          accept=".pdf,application/pdf"
          className="sr-only"
          onChange={handlePdfSelect}
          disabled={loading || atCapacity || pdfLoading}
        />

        <section className="space-y-4 border-b border-slate-100 pb-5">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-blue-700">Routing</p>
              <h2 className="mt-1 text-lg font-semibold text-slate-950">先判断批改路径</h2>
              <p className="mt-1 text-sm text-slate-500 [overflow-wrap:anywhere]">
                系统会优先尝试 Past Paper 匹配；不确定时会回退开放 AI 批改。
              </p>
            </div>
            <span className="w-fit rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-600">
              默认自动识别
            </span>
          </div>

          <div
            role="radiogroup"
            aria-label="上传类型"
            className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4"
          >
            {INTENT_OPTIONS.map((option) => {
              const selected = uploadIntent === option.value
              return (
                <button
                  key={option.value}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  onClick={() => setUploadIntent(option.value)}
                  className={`min-h-[5.75rem] min-w-0 rounded-lg border px-3 py-3 text-left transition ${
                    selected
                      ? 'border-blue-500 bg-blue-50 text-blue-950 ring-1 ring-blue-200'
                      : 'border-slate-200 bg-white text-slate-700 hover:border-blue-200 hover:bg-slate-50'
                  }`}
                >
                  <span className="flex items-start justify-between gap-3">
                    <span className="min-w-0 text-sm font-semibold [overflow-wrap:anywhere]">{option.title}</span>
                    <span
                      className={`mt-0.5 h-3 w-3 shrink-0 rounded-full border ${
                        selected ? 'border-blue-600 bg-blue-600 shadow-[inset_0_0_0_2px_white]' : 'border-slate-300'
                      }`}
                      aria-hidden
                    />
                  </span>
                  <span className="mt-1.5 block text-xs leading-5 text-slate-500 [overflow-wrap:anywhere]">
                    {option.description}
                  </span>
                </button>
              )
            })}
          </div>

          {uploadIntent !== 'custom_homework' ? (
            <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,0.8fr)]">
              <label className="block">
                <span className="text-xs font-medium text-slate-600">Paper code（可选）</span>
                <input
                  type="text"
                  value={paperCode}
                  onChange={(e) => setPaperCode(e.target.value)}
                  placeholder="例如 9709/12/M/J/16"
                  className="mt-1 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                />
              </label>
              <label className="block">
                <span className="text-xs font-medium text-slate-600">题号（可选）</span>
                <input
                  type="text"
                  value={questionNumbers}
                  onChange={(e) => setQuestionNumbers(e.target.value)}
                  placeholder="例如 3, 4(a), 7"
                  className="mt-1 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                />
              </label>
              <p className="text-xs leading-5 text-slate-500 [overflow-wrap:anywhere] sm:col-span-2">
                如果上传 Past Paper，包含封面页或填写 paper code 会更快、更准；不填写也可以继续上传。
              </p>
            </div>
          ) : (
            <p className="rounded-md bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-500 [overflow-wrap:anywhere]">
              自定义作业不会强行匹配真题。系统会直接根据题目和学生作答生成反馈。
            </p>
          )}

          <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 pt-4">
            <span className="text-xs font-semibold text-slate-700">上传后你将获得</span>
            {RESULT_EXPECTATIONS.map((item) => (
              <span
                key={item}
                className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-600"
              >
                {item}
              </span>
            ))}
          </div>
        </section>

        {/* ============ Image upload section ============ */}
        <div>
          <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-blue-700">Upload</p>
              <h2 className="mt-1 text-lg font-semibold text-slate-950">上传作业</h2>
              <p className="mt-1 text-sm text-slate-500">
                支持拍照、图片和 PDF。预识别完成后即可开始批改。
              </p>
            </div>
            <div className="flex flex-wrap gap-2 text-xs text-slate-500">
              <span className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1">最多 {MAX_FILES} 张</span>
              <span className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1">单张 20 MB</span>
              <span className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1">PDF 80 MB</span>
            </div>
          </div>

          {files.length === 0 ? (
            <>
            {/* Mobile: single combined picker (native sheet already shows image/camera/pdf) */}
            <div className="sm:hidden">
              <input
                ref={mobileCombinedInputRef}
                type="file"
                accept="image/*,application/pdf,.pdf"
                multiple
                className="sr-only"
                onChange={handleMobileCombinedSelect}
                disabled={loading || pdfLoading}
              />
              <button
                type="button"
                onClick={() => mobileCombinedInputRef.current?.click()}
                disabled={loading || pdfLoading}
                className="flex w-full items-center justify-center gap-2.5 rounded-lg border border-dashed border-blue-300 bg-blue-50 px-6 py-8 text-sm font-semibold text-blue-800 transition hover:border-blue-500 hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="h-6 w-6">
                  <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
                  <polyline points="17 8 12 3 7 8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </svg>
                上传作业（图片或 PDF）
              </button>
              <p className="mt-2 text-center text-xs text-slate-500">
                支持拍照 / 从相册选择 / 选择 PDF · 最多 {MAX_FILES} 张 · 单张 20 MB
              </p>
            </div>

            {/* Desktop / tablet: drag-drop + split buttons */}
            <div
              onDragEnter={handleDragEnter}
              onDragLeave={handleDragLeave}
              onDragOver={handleDragOver}
              onDrop={handleDrop}
              className={`hidden rounded-lg border px-6 py-10 transition sm:block ${
                loading || pdfLoading
                  ? 'cursor-not-allowed border-slate-200 bg-slate-50 opacity-60'
                  : isDragOver
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-slate-200 bg-slate-50/70 hover:border-blue-300 hover:bg-blue-50/30'
              }`}
            >
              {isDragOver ? (
                <p className="text-center text-base font-medium text-blue-600">松开以上传</p>
              ) : (
                <>
                  <div className="flex flex-col items-center gap-3 sm:flex-row sm:justify-center sm:gap-4">
                    {/* Camera button */}
                    <label
                      className={`inline-flex w-full cursor-pointer items-center justify-center gap-2.5 rounded-md border border-slate-200 bg-white px-5 py-3.5 text-sm font-semibold text-slate-800 shadow-sm transition hover:border-blue-400 hover:bg-blue-50 hover:text-blue-700 sm:w-auto ${
                        loading || pdfLoading ? 'pointer-events-none opacity-50' : ''
                      }`}
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5">
                        <path d="M23 19a2 2 0 01-2 2H3a2 2 0 01-2-2V8a2 2 0 012-2h4l2-3h6l2 3h4a2 2 0 012 2z" />
                        <circle cx="12" cy="13" r="4" />
                      </svg>
                      拍照上传
                      <input
                        ref={cameraInputRef}
                        type="file"
                        accept="image/*"
                        capture="environment"
                        className="sr-only"
                        onChange={handleCameraCapture}
                        disabled={loading || atCapacity || pdfLoading}
                      />
                    </label>

                    <span className="hidden text-xs text-slate-400 sm:block">或</span>
                    <span className="block text-center text-xs text-slate-400 sm:hidden">或</span>

                    {/* Image upload button */}
                    <button
                      type="button"
                      onClick={openFilePicker}
                      disabled={loading || pdfLoading}
                      className="inline-flex w-full items-center justify-center gap-2.5 rounded-md border border-slate-200 bg-white px-5 py-3.5 text-sm font-semibold text-slate-800 shadow-sm transition hover:border-blue-400 hover:bg-blue-50 hover:text-blue-700 disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
                    >
                      {/* Image icon */}
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5">
                        <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                        <circle cx="8.5" cy="8.5" r="1.5" />
                        <polyline points="21 15 16 10 5 21" />
                      </svg>
                      选择图片
                    </button>
                  </div>

                  <p className="mt-4 text-center text-xs text-slate-500">
                    支持拖拽上传 · JPG / PNG / WebP / HEIC · 单张最大 20 MB · 最多 {MAX_FILES} 张
                  </p>
                </>
              )}
            </div>
            </>
          ) : (
            <div
              onDragEnter={handleDragEnter}
              onDragLeave={handleDragLeave}
              onDragOver={handleDragOver}
              onDrop={handleDrop}
              className={`rounded-lg border border-slate-200 bg-slate-50/70 p-3 transition ${isDragOver && canAddMore ? 'ring-2 ring-blue-400 ring-offset-2' : ''}`}
            >
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <p className={`text-sm ${countClass}`}>已选择 {files.length}/{MAX_FILES} 张</p>
                <p className="text-xs text-slate-500">可继续拖拽追加，或裁剪单张图片</p>
              </div>

              <div className="flex flex-wrap items-start gap-3">
                {files.map((file, i) => (
                  <FilePreviewTile
                    key={`${file.name}-${file.size}-${i}`}
                    file={file}
                    previewUrl={previewUrls[i]}
                    removable={!loading}
                    onRemove={() => handleRemoveAt(i)}
                    onEdit={() => handleStartCrop(i)}
                  />
                ))}

                {!atCapacity && (
                  <div className="flex gap-2">
                    {/* Camera add button */}
                    <label
                      className={`flex h-24 w-24 shrink-0 cursor-pointer flex-col items-center justify-center rounded-md border border-dashed border-slate-300 bg-white text-slate-400 transition hover:border-blue-400 hover:bg-blue-50 hover:text-blue-600 ${
                        loading || pdfLoading ? 'pointer-events-none opacity-50' : ''
                      }`}
                      aria-label="拍照添加"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5">
                        <path d="M23 19a2 2 0 01-2 2H3a2 2 0 01-2-2V8a2 2 0 012-2h4l2-3h6l2 3h4a2 2 0 012 2z" />
                        <circle cx="12" cy="13" r="4" />
                      </svg>
                      <span className="mt-0.5 text-[10px]">拍照</span>
                      <input
                        type="file"
                        accept="image/*"
                        capture="environment"
                        className="sr-only"
                        onChange={handleCameraCapture}
                        disabled={loading || atCapacity || pdfLoading}
                      />
                    </label>

                    {/* File add button */}
                    <button
                      type="button"
                      onClick={openFilePicker}
                      disabled={loading || pdfLoading}
                      className="flex h-24 w-24 shrink-0 flex-col items-center justify-center rounded-md border border-dashed border-slate-300 bg-white text-slate-400 transition hover:border-blue-400 hover:bg-blue-50 hover:text-blue-600 disabled:cursor-not-allowed disabled:opacity-50"
                      aria-label="选择图片添加"
                    >
                      <span className="text-2xl font-light">+</span>
                      <span className="mt-0.5 text-[10px]">图片</span>
                    </button>
                  </div>
                )}
              </div>

              <p className="mt-3 text-xs text-slate-500">
                {isDragOver && canAddMore ? '松开以追加图片' : '可拖拽更多图片到此处，或点击拍照 / 添加图片'}
              </p>
            </div>
          )}
        </div>

        {/* ============ PDF upload section (desktop only; mobile uses combined picker) ============ */}
        <div className={files.length === 0 ? 'hidden sm:block' : ''}>
          <div className="relative flex items-center py-1">
            <div className="flex-1 border-t border-slate-200" />
            <span className="px-3 text-xs text-slate-400">或</span>
            <div className="flex-1 border-t border-slate-200" />
          </div>

          <button
            type="button"
            onClick={() => {
              if (canAddMore && !pdfLoading) pdfInputRef.current?.click()
            }}
            disabled={loading || atCapacity || pdfLoading}
            className={`mt-3 flex w-full items-center gap-4 rounded-lg border px-5 py-5 text-left transition ${
              loading || atCapacity || pdfLoading
                ? 'cursor-not-allowed border-slate-200 bg-slate-50 opacity-60'
                : 'cursor-pointer border-slate-200 bg-white hover:border-blue-300 hover:bg-blue-50/40'
            }`}
          >
            {/* PDF icon */}
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-md bg-red-50 text-red-500">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="h-7 w-7"
              >
                <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="9" y1="15" x2="15" y2="15" />
                <line x1="9" y1="11" x2="15" y2="11" />
              </svg>
            </div>

            <div className="min-w-0 flex-1">
              <span className="block text-sm font-semibold text-slate-900">
                {pdfLoading
                  ? pdfProgress
                    ? `正在转换 PDF… ${pdfProgress.current} / ${pdfProgress.total} 页`
                    : '正在转换 PDF 页面…'
                  : '上传 PDF 文件'}
              </span>
              <span className="mt-0.5 block text-xs text-slate-500">
                16 页内默认自动拆图；长 PDF 或真题卷会先进入选页模式 · 文件最大 {MAX_LARGE_PDF_BYTES / 1024 / 1024} MB
              </span>
            </div>

            {pdfLoading && (
              <div className="h-5 w-5 shrink-0 animate-spin rounded-full border-2 border-slate-300 border-t-blue-600" />
            )}
          </button>
        </div>

        {/* ============ PDF conversion progress banner ============ */}
        {pdfLoading && pdfProgress ? (
          <div
            className="fixed bottom-20 left-1/2 z-50 w-[min(92vw,420px)] -translate-x-1/2 rounded-lg border border-blue-200 bg-white px-4 py-3 shadow-lg"
            role="status"
            aria-live="polite"
          >
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2.5 min-w-0">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center">
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-blue-200 border-t-blue-600" />
                </span>
                <span className="truncate text-sm font-medium text-slate-950">
                  正在转换 PDF 页面…
                </span>
              </div>
              <span className="shrink-0 font-mono text-xs font-semibold tabular-nums text-blue-600">
                {pdfProgress.current} / {pdfProgress.total}
              </span>
            </div>
            <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-blue-100">
              <div
                className="h-full bg-blue-600 transition-[width] duration-300 ease-out"
                style={{
                  width:
                    pdfProgress.total > 0
                      ? `${Math.min(100, (pdfProgress.current / pdfProgress.total) * 100)}%`
                      : '0%',
                }}
              />
            </div>
            <p className="mt-1.5 text-[11px] text-slate-500">
              已转好的页面在后台提前识别，批改时无需再等
            </p>
          </div>
        ) : null}

        {/* ============ Batch messages toast ============ */}
        {batchMessagesToast}

        {/* ============ Action buttons ============ */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          {files.length > 0 ? (
            <button
              type="button"
              onClick={loading ? handleCancel : handleResetUpload}
              className={`inline-flex items-center justify-center rounded-md px-4 py-2.5 text-sm font-medium transition sm:min-w-[120px] ${
                loading
                ? 'border border-red-200 bg-red-50 text-red-700 hover:bg-red-100'
                  : 'border border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
              }`}
            >
              {loading ? '取消批改' : '重新上传'}
            </button>
          ) : (
            <div className="hidden sm:block" aria-hidden />
          )}

          <button
            type="submit"
            disabled={!canSubmit}
            className="w-full rounded-md bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300 sm:w-auto sm:min-w-[160px]"
          >
            {loading ? '分析中…' : files.length === 0 ? '预览' : `预览（${files.length} 张）`}
          </button>
        </div>
      </form>

      {/* ============ Crop modal (per-tile edit) ============ */}
      {pendingCropUrl && (
        <ImageCropper
          imageUrl={pendingCropUrl}
          onConfirm={handleCropConfirm}
          onCancel={handleCropCancel}
        />
      )}

      {/* ============ Full-screen preview (swipe + zoom) ============ */}
      {showPreview && (
        <ImagesPreview
          files={files}
          prepareStates={prepareStates}
          onBack={() => setShowPreview(false)}
          onStart={handlePreviewStart}
        />
      )}
    </>
  )
}
