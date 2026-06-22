import { readFile } from 'node:fs/promises'

import ts from 'typescript'

const sourceUrl = new URL('../src/lib/practiceRecommendationContext.ts', import.meta.url)
const source = await readFile(sourceUrl, 'utf8')
const { outputText } = ts.transpileModule(source, {
  compilerOptions: {
    target: ts.ScriptTarget.ES2023,
    module: ts.ModuleKind.ESNext,
    verbatimModuleSyntax: true,
  },
})

const {
  buildPracticeContext,
  buildPracticeRequest,
  difficultyRangeFromPracticeResult,
} = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)

const UPLOAD_STEP_QUESTION_NUMBER = '\u672c\u6b21\u4e0a\u4f20'

function assertEqual(actual, expected, label) {
  if (actual !== expected) {
    throw new Error(`${label}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`)
  }
}

function assertDeepEqual(actual, expected, label) {
  const actualJson = JSON.stringify(actual)
  const expectedJson = JSON.stringify(expected)
  if (actualJson !== expectedJson) {
    throw new Error(`${label}: expected ${expectedJson}, got ${actualJson}`)
  }
}

function analyzeRequest(overrides = {}) {
  return {
    images: [],
    ...overrides,
  }
}

function resolutionStep(overrides = {}) {
  return {
    question_number: UPLOAD_STEP_QUESTION_NUMBER,
    step_type: 'decide',
    title: 'Resolve paper',
    summary: 'Paper resolved',
    status: 'completed',
    detail: {},
    ...overrides,
  }
}

function submitAnswerResult({ score, fullScore, isCorrect = false }) {
  return {
    grade_result: {
      score,
      full_score: fullScore,
      is_correct: isCorrect,
    },
  }
}

const paperCodeCases = [
  ['9709/12/M/J/16', 1],
  ['9709_s16_qp_12', 1],
  ['9709_s16_12', 1],
  ['9709_s16_ms_51.pdf', 5],
  ['9709 32 ON 2023', 3],
  ['', null],
  ['9709_s16', null],
  ['not-a-paper-code', null],
]

for (const [paperCode, expectedPaperNum] of paperCodeCases) {
  const context = buildPracticeContext(analyzeRequest({ paper_code: paperCode }), [])
  assertEqual(context.paper_num, expectedPaperNum, `paper_code ${paperCode || '<empty>'}`)
}

const overrideContext = buildPracticeContext(
  analyzeRequest({ paper_code: '9709/12/M/J/16' }),
  [
    resolutionStep({
      detail: { catalog_match: { paper_num: 5 } },
      match_confidence: 'high',
      grading_route: 'past_paper_mark_scheme',
    }),
  ],
)
assertEqual(overrideContext.paper_num, 5, 'agent evidence overrides paper_code fallback')

const latestContext = buildPracticeContext(
  analyzeRequest({ paper_code: '9709/12/M/J/16' }),
  [
    resolutionStep({
      detail: { catalog_match: { paper_num: 1 } },
      match_confidence: 'high',
    }),
    resolutionStep({
      detail: { catalog_match: { paper_num: 3 } },
      match_confidence: 'medium',
    }),
  ],
)
assertEqual(latestContext.paper_num, 3, 'latest resolution step wins')
assertEqual(latestContext.match_confidence, 'medium', 'latest resolution metadata wins')

for (const intent of ['full_past_paper_pdf', 'partial_past_paper_pages']) {
  const context = buildPracticeContext(analyzeRequest({ upload_intent: intent }), [])
  assertEqual(context.upload_intent, intent, `upload intent ${intent}`)
}

const practiceRequest = buildPracticeRequest({
  request: analyzeRequest({
    upload_intent: 'full_past_paper_pdf',
    paper_code: '9709_s16_qp_12',
    question_numbers: '4',
  }),
  agentSteps: [],
  summary: {
    priority_topics: [{ topic: 'quadratics', subtopic: 'roots', chapter: 'P1', error_count: 2 }],
    knowledge_tags_summary: { quadratics: 2 },
  },
  questions: [
    {
      question_number: '4',
      score: 2,
      full_score: 5,
      is_correct: false,
      unanswered: false,
      error_type: 'missing_solution',
      knowledge_tags: ['quadratics'],
      needs_review: true,
    },
  ],
  excludeIds: [101, 102],
  preferredDifficultyMin: 2,
  preferredDifficultyMax: 4,
  confirmedByUser: true,
})

assertEqual(practiceRequest.context.upload_intent, 'full_past_paper_pdf', 'request intent mapping')
assertEqual(practiceRequest.context.paper_num, 1, 'request context paper number')
assertEqual(practiceRequest.context.confirmed_by_user, true, 'request confirmed flag')
assertEqual(practiceRequest.count, 3, 'request recommendation count')
assertDeepEqual(practiceRequest.exclude_ids, [101, 102], 'request exclude ids')
assertDeepEqual(practiceRequest.questions[0], {
  question_number: '4',
  score: 2,
  full_score: 5,
  is_correct: false,
  unanswered: false,
  error_type: 'missing_solution',
  knowledge_tags: ['quadratics'],
  needs_review: true,
}, 'request source question mapping')

assertDeepEqual(
  difficultyRangeFromPracticeResult(submitAnswerResult({ score: 0, fullScore: 5, isCorrect: true })),
  [3, 5],
  'correct result uses higher difficulty',
)
assertDeepEqual(
  difficultyRangeFromPracticeResult(submitAnswerResult({ score: 4, fullScore: 5 })),
  [3, 5],
  'high score uses higher difficulty',
)
assertDeepEqual(
  difficultyRangeFromPracticeResult(submitAnswerResult({ score: 2, fullScore: 5 })),
  [2, 3],
  'partial score uses middle difficulty',
)
assertDeepEqual(
  difficultyRangeFromPracticeResult(submitAnswerResult({ score: 1, fullScore: 5 })),
  [1, 2],
  'low score uses lower difficulty',
)

console.log(JSON.stringify({ status: 'ok', checked: paperCodeCases.length + 12 }, null, 2))
