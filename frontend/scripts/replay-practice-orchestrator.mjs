import { readFile } from 'node:fs/promises'

const root = new URL('../', import.meta.url)
const component = await readFile(new URL('src/components/practice/PracticeRecommendations.tsx', root), 'utf8')
const fixture = await readFile(new URL('src/fixtures/practiceOrchestratorReplay.ts', root), 'utf8')
const replayPage = await readFile(new URL('src/pages/PracticeRecommendationsReplayPage.tsx', root), 'utf8')

for (const snippet of ['下一步练习', '要不要继续练这个点', '给我 2-3 道类似题', '调整下一题']) {
  if (!component.includes(snippet)) {
    throw new Error(`PracticeRecommendations missing expected student-facing snippet: ${snippet}`)
  }
}

for (const eventName of [
  'ui_practice_recommendation_seen',
  'ui_practice_recommendation_confirmed',
  'ui_practice_recommendation_dismissed',
  'ui_practice_started',
  'ui_practice_answer_submitted',
  'ui_practice_result_viewed',
  'ui_practice_next_adjusted',
]) {
  if (!component.includes(eventName)) {
    throw new Error(`PracticeRecommendations missing evaluation event: ${eventName}`)
  }
}

for (const forbidden of ['student_answer', 'working_steps']) {
  const eventPayloadPattern = new RegExp(`trackEvent\\([^)]*${forbidden}`, 's')
  if (eventPayloadPattern.test(component)) {
    throw new Error(`Practice evaluation event must not include raw ${forbidden}`)
  }
}

for (const raw of ['>think<', '>act<', '>observe<', '>decide<', '>final<']) {
  if (component.toLowerCase().includes(raw)) {
    throw new Error(`Raw agent label leaked into practice UI: ${raw}`)
  }
}

const replayComponentCount = replayPage.match(/<PracticeRecommendations\b/g)?.length ?? 0
if (replayComponentCount < 3) {
  throw new Error(`Practice recommendations replay should render at least 3 component states, found: ${replayComponentCount}`)
}

const rawLabelPattern = />\s*(think|act|observe|decide|final)\s*</i
if (rawLabelPattern.test(component)) {
  throw new Error('Raw agent label leaked into practice UI text content')
}

const visibleLabelAssignmentPattern = /\b(label|title|summary)\s*:\s*(['"])(think|act|observe|decide|final)\2/i
if (visibleLabelAssignmentPattern.test(component)) {
  throw new Error('Raw agent label assigned to a visible practice UI surface')
}

if (component.includes('step_type')) {
  throw new Error('PracticeRecommendations should not render or inspect raw agent step_type values')
}

for (const mode of ['auto', 'ask_first', 'none']) {
  if (!fixture.includes(`recommendation_mode: '${mode}'`)) {
    throw new Error(`Replay fixture missing mode: ${mode}`)
  }
}

console.log(JSON.stringify({ status: 'ok', checked: 'practice-orchestrator-replay' }, null, 2))
