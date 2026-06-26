import { readFile } from 'node:fs/promises'

const root = new URL('../', import.meta.url)
const uploadForm = await readFile(new URL('src/components/UploadForm.tsx', root), 'utf8')
const apiClient = await readFile(new URL('src/api/client.ts', root), 'utf8')

if (uploadForm.includes('kickoffPrepare')) {
  throw new Error('UploadForm should not kick off prepare-upload while the user is selecting images')
}

if (uploadForm.includes('prepareUpload(')) {
  throw new Error('UploadForm should not call prepareUpload for normal image uploads')
}

for (const blockedText of ['等待全部', '识别中 ${readyCount}', 'disabled={!allReady}']) {
  if (uploadForm.includes(blockedText)) {
    throw new Error(`Preview start should not be blocked by pre-recognition: ${blockedText}`)
  }
}

if (!uploadForm.includes('fast_batch: true')) {
  throw new Error('UploadForm should submit image analysis in fast_batch mode')
}

if (!apiClient.includes("form.append('fast_batch', 'true')")) {
  throw new Error('API client should pass fast_batch=true to analyze-homework-stream')
}

console.log(JSON.stringify({ status: 'ok', checked: 'fast-upload-flow' }, null, 2))
