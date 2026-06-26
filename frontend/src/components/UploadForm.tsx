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
const PREPARE_UPLOAD_CONCURRENCY = 10
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
    title: '帮我识别',
    description: '直接上传，系统会先判断材料类型',
  },
  {
    value: 'past_paper',
    title: 'Past Paper / 真题卷',
    description: '可填写 paper code，优先匹配评分规则',
  },
  {
    value: 'custom_homework',
    title: '老师布置的作业',
    description: '按题目和作答直接批改',
  },
  {
    value: 'answer_pages_only',
    title: '只有答案页',
    description: '缺题目时会在报告里提示',
  },
]

function CameraIcon({ className = 'h-6 w-6' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M4 7.5h3.2l1.5-2h6.6l1.5 2H20a2 2 0 0 1 2 2V18a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V9.5a2 2 0 0 1 2-2Z" />
      <circle cx="12" cy="13.5" r="3.5" />
    </svg>
  )
}

function ImageIcon({ className = 'h-6 w-6' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <circle cx="8.5" cy="9.5" r="1.5" />
      <path d="m4 17 4.6-4.6a1.4 1.4 0 0 1 2 0L13 14.8l2.2-2.2a1.4 1.4 0 0 1 2 0L21 16.4" />
    </svg>
  )
}

function PdfIcon({ className = 'h-6 w-6' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M7 3h6l4 4v14H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" />
      <path d="M13 3v5h5" />
      <path d="M8 15h8" />
      <path d="M8 18h5" />
    </svg>
  )
}

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
          className="absolute left-1 top-1 flex h-6 w-6 items-center justify-center rounded-full bg-slate-900/85 text-white opacity-100 shadow transition hover:bg-black md:opacity-0 md:group-hover:opacity-100 disabled:opacity-40"
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
        className="absolute right-1 top-1 flex h-6 w-6 items-center justify-center rounded-full bg-slate-900/85 text-sm leading-none text-white opacity-100 shadow transition hover:bg-black md:opacity-0 md:group-hover:opacity-100 disabled:opacity-40"
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
  const statusText = processingCount > 0
    ? `可先开始；后台预识别 ${readyCount}/${files.length}`
    : readyCount > 0
      ? `已提前识别 ${readyCount}/${files.length}，可开始批改`
      : '可开始批改，系统将在下一步统一识别'

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
          title="开始批改"
          className="inline-flex shrink-0 items-center whitespace-nowrap rounded-md bg-slate-950 px-3 py-1.5 text-[13px] font-semibold text-white shadow-sm transition hover:bg-black sm:px-4 sm:text-sm"
        >
          开始批改
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
                  ? 'bg-white'
                  : s === 'failed'
                    ? 'bg-white/50'
                    : s === 'processing'
                      ? 'bg-white/70 animate-pulse'
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
  const dragDepthRef = useRef(0)
  const prepareControllersRef = useRef<Map<File, AbortController>>(new Map())

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

  useEffect(() => {
    const current = new Set(files)
    for (const [file, controller] of prepareControllersRef.current.entries()) {
      if (!current.has(file)) {
        controller.abort()
        prepareControllersRef.current.delete(file)
      }
    }
  }, [files])

  useEffect(() => {
    return () => {
      for (const controller of prepareControllersRef.current.values()) {
        controller.abort()
      }
      prepareControllersRef.current.clear()
    }
  }, [])

  useEffect(() => {
    const pending = files.filter(
      (file) => !prepareStates.has(file) && !prepareControllersRef.current.has(file),
    )
    if (pending.length === 0) return

    setPrepareStates((state) => {
      const next = new Map(state)
      for (const file of pending) {
        next.set(file, { status: 'processing' })
      }
      return next
    })

    let cursor = 0
    const workerCount = Math.min(PREPARE_UPLOAD_CONCURRENCY, pending.length)
    const runWorker = async () => {
      while (cursor < pending.length) {
        const file = pending[cursor]
        cursor += 1
        const controller = new AbortController()
        prepareControllersRef.current.set(file, controller)
        try {
          const result = await prepareUpload(file, '', controller.signal)
          if (!filesRef.current.includes(file)) continue
          setPrepareStates((state) => {
            const next = new Map(state)
            next.set(file, { status: 'ready', uploadId: result.upload_id })
            return next
          })
        } catch (err) {
          if (controller.signal.aborted || !filesRef.current.includes(file)) continue
          setPrepareStates((state) => {
            const next = new Map(state)
            next.set(file, { status: 'failed' })
            return next
          })
        } finally {
          prepareControllersRef.current.delete(file)
        }
      }
    }

    for (let i = 0; i < workerCount; i += 1) {
      void runWorker()
    }
  }, [files, prepareStates])

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

  const addFilesFromList = (list: FileList | File[] | null) => {
    if (!list || list.length === 0) return
    const incoming = Array.from(list)
    const current = filesRef.current
    const { next, messages } = processIncomingFiles(incoming, current)
    const addedCount = next.length - current.length
    trackEvent('ui_file_selected', {
      incoming_count: incoming.length,
      accepted_count: Math.max(0, addedCount),
      file_count: next.length,
      file_types: incoming.map((f) => f.type || f.name.split('.').pop()?.toLowerCase() || 'unknown'),
      total_bytes: incoming.reduce((a, f) => a + f.size, 0),
      upload_intent: uploadIntent,
      at_capacity: next.length >= MAX_FILES,
      rejected_count: Math.max(0, incoming.length - addedCount),
    })
    if (addedCount === 0 && messages.length === 0) return
    setFiles(next)
    filesRef.current = next
    if (messages.length > 0) setBatchMessages(messages)
  }

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    addFilesFromList(e.target.files)
    e.target.value = ''
  }

  const handleRemoveAt = (index: number) => {
    setFiles((prev) => {
      const removed = prev[index]
      if (removed) {
        trackEvent('ui_file_removed', {
          file_count_before: prev.length,
          file_count_after: Math.max(0, prev.length - 1),
          file_type: removed.type || removed.name.split('.').pop()?.toLowerCase() || 'unknown',
          upload_intent: uploadIntent,
        })
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
    } else {
      addFilesFromList([croppedFile])
    }
  }

  const handleCropCancel = () => {
    if (pendingCropUrl) URL.revokeObjectURL(pendingCropUrl)
    setPendingCropUrl(null)
    setEditingIndex(null)
  }

  /* ---- Open preview: local preview only; recognition happens when analysis starts ---- */
  const openPreview = () => {
    if (files.length === 0 || loading || pdfLoading) return
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
      fast_batch: true,
    })
  }

  /**
   * Convert a PDF into page images and add each rendered page immediately.
   * The server now recognizes pages in one fast batch during analysis instead
   * of pre-recognizing every image while the user is still choosing files.
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
      trackEvent('ui_pdf_selected', {
        page_count: pageCount,
        file_bytes: file.size,
        upload_intent: uploadIntent,
        large_pdf: useLargePdfMode,
      })

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
          preview_count: prepared.preview_pages.length,
          default_selected_count: prepared.preview_pages.filter((p) => p.selected_by_default).length,
          upload_intent: uploadIntent,
          match_confidence: prepared.paper_resolution?.match_confidence,
          match_source: prepared.paper_resolution?.match_source,
          grading_route: prepared.paper_resolution?.grading_route,
          needs_confirmation: prepared.paper_resolution?.needs_user_confirmation,
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
    files.length >= MAX_FILES ? 'font-medium text-slate-950' : 'text-slate-600'

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
        default_selected_count: largePdfSession?.preview_pages.filter((p) => p.selected_by_default).length,
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
        fast_batch: true,
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

  const renderUploadTray = (compact = false) => {
    const actionSize = compact ? 'h-8 w-8' : 'h-9 w-9 sm:h-10 sm:w-10'
    const iconSize = compact ? 'h-4 w-4' : 'h-5 w-5'
    const actionClass = `${actionSize} upload-action-button group relative inline-flex shrink-0 items-center justify-center rounded-full text-slate-950 transition duration-150 ease-out hover:bg-slate-100 active:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-950 disabled:cursor-not-allowed disabled:opacity-35`
    const tooltipClass = 'pointer-events-none absolute -top-8 left-1/2 hidden -translate-x-1/2 whitespace-nowrap text-xs font-medium text-slate-500 opacity-0 transition group-hover:opacity-100 sm:block'

    return (
      <div className="flex flex-col items-center gap-2">
        <div
          className={`inline-flex items-center justify-center gap-0.5 rounded-full border border-slate-200 bg-white shadow-[0_10px_24px_rgba(15,23,42,0.08)] ${
            compact ? 'p-1' : 'p-1.5'
          }`}
          aria-label="上传入口"
        >
          <label className={`${actionClass} ${loading || atCapacity || pdfLoading ? 'pointer-events-none opacity-35' : 'cursor-pointer'}`}>
            <span className={tooltipClass}>拍照</span>
            <CameraIcon className={iconSize} />
            <input
              ref={cameraInputRef}
              type="file"
              accept="image/*"
              capture="environment"
              aria-label="拍照上传作业"
              className="sr-only"
              onChange={handleCameraCapture}
              disabled={loading || atCapacity || pdfLoading}
            />
          </label>

          <button
            type="button"
            onClick={openFilePicker}
            disabled={loading || atCapacity || pdfLoading}
            className={actionClass}
            aria-label="选择图片"
            title="选择图片"
          >
            <span className={tooltipClass}>图片</span>
            <ImageIcon className={iconSize} />
          </button>

          <button
            type="button"
            onClick={() => {
              if (canAddMore && !pdfLoading) pdfInputRef.current?.click()
            }}
            disabled={loading || atCapacity || pdfLoading}
            className={actionClass}
            aria-label="选择 PDF"
            title="选择 PDF"
          >
            <span className={tooltipClass}>PDF</span>
            <PdfIcon className={iconSize} />
          </button>
        </div>

        {!compact ? (
          <p className="text-center text-xs leading-5 text-slate-500">
            拍一张、选图片或上传 PDF 都可以
          </p>
        ) : null}
      </div>
    )
  }

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
          aria-label="选择作业图片"
          className="sr-only"
          onChange={handleFileInputChange}
          disabled={loading || atCapacity || pdfLoading}
        />
        <input
          ref={pdfInputRef}
          type="file"
          accept=".pdf,application/pdf"
          aria-label="选择 PDF 文件"
          className="sr-only"
          onChange={handlePdfSelect}
          disabled={loading || atCapacity || pdfLoading}
        />

        <section className="space-y-4 border-b border-slate-100 pb-5">
          <div className="space-y-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h2 className="text-lg font-semibold text-slate-950">选择材料类型</h2>
                <p className="mt-1 text-sm leading-6 text-slate-500 [overflow-wrap:anywhere]">
                  不确定也可以直接上传，系统会判断。
                </p>
              </div>
              <span className="w-fit rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-600">
                自动识别
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
                    aria-label={`${option.title}：${option.description}`}
                    onClick={() => setUploadIntent(option.value)}
                    className={`min-h-16 min-w-0 rounded-lg border px-3 py-3 text-left transition ${
                      selected
                        ? 'border-slate-950 bg-slate-50 text-slate-950 ring-1 ring-slate-950'
                        : 'border-slate-200 bg-white text-slate-700 hover:border-slate-400 hover:bg-slate-50'
                    }`}
                  >
                    <span className="flex items-start justify-between gap-3">
                      <span className="min-w-0 text-sm font-semibold [overflow-wrap:anywhere]">{option.title}</span>
                      <span
                        className={`mt-0.5 h-3 w-3 shrink-0 rounded-full border ${
                          selected ? 'border-slate-950 bg-slate-950 shadow-[inset_0_0_0_2px_white]' : 'border-slate-300'
                        }`}
                        aria-hidden
                      />
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
                    className="mt-1 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-slate-950 focus:ring-2 focus:ring-slate-200"
                  />
                </label>
                <label className="block">
                  <span className="text-xs font-medium text-slate-600">题号（可选）</span>
                  <input
                    type="text"
                    value={questionNumbers}
                    onChange={(e) => setQuestionNumbers(e.target.value)}
                    placeholder="例如 3, 4(a), 7"
                    className="mt-1 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-slate-950 focus:ring-2 focus:ring-slate-200"
                  />
                </label>
              </div>
            ) : (
              null
            )}

            <div className="rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-600">
              只有答案页也可以上传；缺题目时报告里会提示。
            </div>
          </div>
        </section>

        {/* ============ Image upload section ============ */}
        <div>
          <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-950">上传作业</h2>
              <p className="mt-1 text-sm text-slate-500">
                支持拍照、图片和 PDF。
              </p>
            </div>
            <div className="flex flex-wrap gap-2 text-xs text-slate-500">
              <span className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1">最多 {MAX_FILES} 张</span>
              <span className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1">单张 20 MB</span>
              <span className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1">PDF 80 MB</span>
            </div>
          </div>

          {files.length === 0 ? (
            <div
              onDragEnter={handleDragEnter}
              onDragLeave={handleDragLeave}
              onDragOver={handleDragOver}
              onDrop={handleDrop}
              className={`rounded-lg py-5 transition ${
                loading || pdfLoading
                  ? 'cursor-not-allowed opacity-60'
                  : isDragOver
                    ? 'bg-slate-50 ring-1 ring-slate-950'
                    : ''
              }`}
            >
              {renderUploadTray()}
              <p className="mt-3 text-center text-xs text-slate-500">
                {isDragOver ? '松开以上传' : `支持拖拽图片 · 最多 ${MAX_FILES} 张 · PDF 最大 ${MAX_LARGE_PDF_BYTES / 1024 / 1024} MB`}
              </p>
            </div>
          ) : (
            <div
              onDragEnter={handleDragEnter}
              onDragLeave={handleDragLeave}
              onDragOver={handleDragOver}
              onDrop={handleDrop}
              className={`rounded-lg border border-slate-200 bg-slate-50/60 p-3 transition ${
                isDragOver && canAddMore ? 'ring-2 ring-slate-950 ring-offset-2' : ''
              }`}
            >
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className={`text-sm ${countClass}`}>已选择 {files.length}/{MAX_FILES} 张</p>
                  <p className="mt-1 text-xs text-slate-500">
                    可继续添加，或点击缩略图左上角裁剪
                  </p>
                </div>
                {!atCapacity ? renderUploadTray(true) : null}
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
              </div>

              <p className="mt-3 text-xs text-slate-500">
                {isDragOver && canAddMore ? '松开以追加图片' : '也可以拖拽更多图片到这里'}
              </p>
            </div>
          )}
        </div>

        {/* ============ PDF conversion progress banner ============ */}
        {pdfLoading && pdfProgress ? (
          <div
            className="fixed bottom-20 left-1/2 z-50 w-[min(92vw,420px)] -translate-x-1/2 rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-lg"
            role="status"
            aria-live="polite"
          >
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2.5 min-w-0">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center">
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-200 border-t-slate-950" />
                </span>
                <span className="truncate text-sm font-medium text-slate-950">
                  正在转换 PDF 页面…
                </span>
              </div>
              <span className="shrink-0 font-mono text-xs font-semibold tabular-nums text-slate-950">
                {pdfProgress.current} / {pdfProgress.total}
              </span>
            </div>
            <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full bg-slate-950 transition-[width] duration-300 ease-out"
                style={{
                  width:
                    pdfProgress.total > 0
                      ? `${Math.min(100, (pdfProgress.current / pdfProgress.total) * 100)}%`
                      : '0%',
                }}
              />
            </div>
            <p className="mt-1.5 text-[11px] text-slate-500">
              已转好的页面会在开始批改后统一快速识别
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
                ? 'border border-slate-300 bg-slate-100 text-slate-950 hover:bg-slate-200'
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
