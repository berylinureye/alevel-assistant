import { readFile } from 'node:fs/promises'

import { getAgentDisplay } from '../src/utils/modelDisplay.ts'

const root = new URL('../', import.meta.url)
const appSource = await readFile(new URL('src/App.tsx', root), 'utf8')
const skeletonSource = await readFile(new URL('src/components/SkeletonQuestionCard.tsx', root), 'utf8')
const questionCardSource = await readFile(new URL('src/components/QuestionCard.tsx', root), 'utf8')

const rawModelTokens = [
  'deepseek',
  'qwen',
  'glm',
  'gpt',
  'claude',
  '内部模型',
  'model_id',
  '批改员 A',
  '批改员 B',
  '批改员 C',
  '复核员 A',
  '复核员 B',
]

for (const agentName of ['DeepSeek-Fast', 'Qwen-Fast', 'GLM-Fast', 'Qwen-Accurate', 'GLM-Thinking']) {
  const display = getAgentDisplay(agentName)
  const visible = `${display.shortName} ${display.roleName} ${display.description}`.toLowerCase()
  for (const token of rawModelTokens) {
    if (visible.includes(token.toLowerCase())) {
      throw new Error(`Agent display leaks raw/internal model wording: ${agentName} -> ${token}`)
    }
  }
}

for (const [fileName, source] of [
  ['App.tsx', appSource],
  ['SkeletonQuestionCard.tsx', skeletonSource],
]) {
  for (const token of ['内部模型已记录', '内部模型：']) {
    if (source.includes(token)) {
      throw new Error(`${fileName} still contains student-visible internal model wording: ${token}`)
    }
  }
}

const requiredQuestionCardSnippets = [
  '学习诊断',
  '本题表现',
  '得分',
  '批改依据',
]

for (const snippet of requiredQuestionCardSnippets) {
  if (!questionCardSource.includes(snippet)) {
    throw new Error(`QuestionCard missing expected diagnosis UI snippet: ${snippet}`)
  }
}

console.log(JSON.stringify({
  status: 'ok',
  checked: {
    modelDisplay: true,
    internalModelWording: true,
    questionDiagnosisShell: true,
  },
}, null, 2))
