import { mkdir, writeFile } from 'node:fs/promises'
import { dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

import { agentStepReplayFixture } from '../src/fixtures/agentStepReplay.ts'
import {
  buildAgentStepViewModels,
  renderAgentStepReplayHtml,
} from '../src/components/agentStepViewModel.ts'

const __dirname = dirname(fileURLToPath(import.meta.url))
const outputPath = '/private/tmp/alevel-agent-step-replay.html'

const viewModels = buildAgentStepViewModels(agentStepReplayFixture)
const html = renderAgentStepReplayHtml(viewModels)

const rawLabels = ['think', 'act', 'observe', 'decide', 'final']
const lowerHtml = html.toLowerCase()
for (const label of rawLabels) {
  if (lowerHtml.includes(`>${label}<`) || lowerHtml.includes(` ${label} `)) {
    throw new Error(`Raw agent step label leaked into replay HTML: ${label}`)
  }
}

const requiredSnippets = [
  '匹配真题',
  '选择批改路径',
  '真题匹配',
  '评分规则 高',
  '上传路由',
  '本地题库',
  '开放批改',
  '已降级',
  '未找到这一题对应的评分规则上下文',
]
for (const snippet of requiredSnippets) {
  if (!html.includes(snippet)) {
    throw new Error(`Replay HTML missing expected snippet: ${snippet}`)
  }
}

const forbiddenSnippets = [
  'debug-only',
  'Paper Resolver',
  'Mark Scheme Router',
  'Upload Router',
  'papers_catalog.csv',
  'MS 高',
  'Could not locate question 99',
]
for (const snippet of forbiddenSnippets) {
  if (html.includes(snippet)) {
    throw new Error(`Replay HTML leaked technical snippet: ${snippet}`)
  }
}

await mkdir(dirname(outputPath), { recursive: true })
await writeFile(outputPath, html, 'utf8')

console.log(JSON.stringify({
  status: 'ok',
  stepsRendered: viewModels.length,
  outputPath,
}, null, 2))
