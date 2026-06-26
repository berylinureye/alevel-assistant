import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

let configured = false

async function getPdfJs() {
  const lib = await import('pdfjs-dist')
  if (!configured) {
    lib.GlobalWorkerOptions.workerSrc = workerUrl
    configured = true
  }
  return lib
}

export interface PdfToImagesOptions {
  scale?: number
  signal?: AbortSignal
  /**
   * Fires once per page as soon as it has been rendered + encoded, BEFORE
   * the next page starts rendering. Use this to kick off prepare-upload
   * immediately so the server can OCR in parallel with rendering the
   * remaining pages. This is the main lever for cutting perceived latency.
   */
  onPage?: (file: File, index: number, total: number) => void
  /**
   * Fires after each page completes (including on page 0 = start). Drives a
   * user-visible progress bar.
   */
  onProgress?: (done: number, total: number) => void
}

async function renderPdfPageToImageFile(
  pdf: Awaited<ReturnType<Awaited<ReturnType<typeof getPdfJs>>['getDocument']>['promise']>,
  file: File,
  pageNumber: number,
  scale: number,
): Promise<File> {
  const page = await pdf.getPage(pageNumber)
  const vp = page.getViewport({ scale })

  const canvas = document.createElement('canvas')
  canvas.width = vp.width
  canvas.height = vp.height
  const ctx = canvas.getContext('2d')
  if (ctx == null) {
    throw new Error('Canvas 初始化失败')
  }

  await page.render({ canvas, canvasContext: ctx, viewport: vp }).promise

  const blob: Blob = await new Promise((r) =>
    canvas.toBlob((b) => r(b!), 'image/jpeg', 0.92),
  )
  canvas.width = 0
  canvas.height = 0

  const base = file.name.replace(/\.pdf$/i, '')
  return new File([blob], `${base}_第${pageNumber}页.jpg`, { type: 'image/jpeg' })
}

export async function getPdfPageCount(file: File): Promise<number> {
  const pdfjsLib = await getPdfJs()
  const buf = await file.arrayBuffer()
  const pdf = await pdfjsLib.getDocument({ data: buf }).promise
  return pdf.numPages
}

export async function pdfPagesToImages(
  file: File,
  pages: number[],
  options: PdfToImagesOptions = {},
): Promise<{ files: File[]; totalPages: number }> {
  const { scale = 1.5, signal, onProgress } = options
  const uniquePages = [...new Set(pages)].sort((a, b) => a - b)
  const pdfjsLib = await getPdfJs()
  const buf = await file.arrayBuffer()
  const pdf = await pdfjsLib.getDocument({ data: buf }).promise
  const totalPages = pdf.numPages
  const files: File[] = []

  if (uniquePages.some((page) => page < 1 || page > totalPages)) {
    throw new Error('选择的 PDF 页码超出范围')
  }

  onProgress?.(0, uniquePages.length)
  for (let i = 0; i < uniquePages.length; i += 1) {
    if (signal?.aborted) break
    files.push(await renderPdfPageToImageFile(pdf, file, uniquePages[i], scale))
    onProgress?.(i + 1, uniquePages.length)
    await new Promise((r) => setTimeout(r, 0))
  }

  return { files, totalPages }
}

/**
 * Render each page of a PDF to a JPEG image File.
 * Returns at most `maxPages` images; remaining pages are reported as `skipped`.
 *
 * Emits pages progressively via `onPage` so the caller can pipeline work
 * (e.g. start uploading page 1 while page 2 is still rendering).
 */
export async function pdfToImages(
  file: File,
  maxPages: number,
  options: PdfToImagesOptions = {},
): Promise<{ files: File[]; totalPages: number; skipped: number }> {
  // scale=1.5 keeps OCR quality intact (≥150 DPI effective for A4) while
  // producing ~55% smaller JPEGs than scale=2 — matters on mobile where
  // rendering 7 full-size thumbnails + uploading them was noticeably laggy.
  const { scale = 1.5, signal, onPage, onProgress } = options
  const pdfjsLib = await getPdfJs()
  const buf = await file.arrayBuffer()
  const pdf = await pdfjsLib.getDocument({ data: buf }).promise

  const totalPages = pdf.numPages
  const count = Math.min(totalPages, maxPages)
  const files: File[] = []
  onProgress?.(0, count)

  for (let i = 1; i <= count; i++) {
    if (signal?.aborted) break
    const pageFile = await renderPdfPageToImageFile(pdf, file, i, scale)
    files.push(pageFile)

    onPage?.(pageFile, i, count)
    onProgress?.(i, count)

    // Yield to the event loop so onPage's prepare-upload fetch() can start
    // firing while we set up the next render — without this the microtask
    // queue drains fully between iterations and prepare is still serial.
    await new Promise((r) => setTimeout(r, 0))
  }

  return { files, totalPages, skipped: totalPages - count }
}
