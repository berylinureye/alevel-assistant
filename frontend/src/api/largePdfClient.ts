import type { LargePdfPrepareResponse, UploadIntent } from '../types'

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/+$/, '') ?? ''

export interface PrepareLargePdfOptions {
  uploadIntent?: UploadIntent
  paperCode?: string
  questionNumbers?: string
  signal?: AbortSignal
}

async function readFetchErrorMessage(res: Response): Promise<string> {
  if (res.status === 502 || res.status === 503 || res.status === 504) {
    return '无法连接到后端服务，请确认服务器已启动（python server.py）'
  }
  const data: unknown = await res.json().catch(() => null)
  if (data && typeof data === 'object') {
    const detail = (data as { detail?: unknown; message?: unknown }).detail
    if (typeof (data as { message?: unknown }).message === 'string') {
      return (data as { message: string }).message
    }
    if (detail && typeof detail === 'object') {
      const message = (detail as { message?: unknown }).message
      if (typeof message === 'string') return message
    }
    if (typeof detail === 'string') return detail
  }
  return `HTTP ${res.status}`
}

export async function prepareLargePdf(
  file: File,
  options: PrepareLargePdfOptions = {},
): Promise<LargePdfPrepareResponse> {
  const form = new FormData()
  form.append('pdf', file, file.name || 'upload.pdf')
  form.append('upload_intent', options.uploadIntent ?? 'full_past_paper_pdf')
  if (options.paperCode?.trim()) form.append('paper_code', options.paperCode.trim())
  if (options.questionNumbers?.trim()) form.append('question_numbers', options.questionNumbers.trim())

  let res: Response
  try {
    res = await fetch(`${API_BASE}/large-pdf/prepare`, {
      method: 'POST',
      body: form,
      signal: options.signal,
    })
  } catch {
    throw new Error('无法连接到后端服务，请确认服务器已启动（python server.py）')
  }

  if (!res.ok) {
    throw new Error(await readFetchErrorMessage(res))
  }
  return res.json()
}
