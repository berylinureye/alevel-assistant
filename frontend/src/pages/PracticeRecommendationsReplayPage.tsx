import { PracticeRecommendations } from '../components/practice/PracticeRecommendations'
import {
  askFirstRecommendationFixture,
  autoRecommendationFixture,
  practiceReplayQuestions,
  practiceReplaySummary,
  unavailableRecommendationFixture,
} from '../fixtures/practiceOrchestratorReplay'
import type { SubmitAnswerResponse } from '../types/practice'

const replayAnswerSubmitter = async (): Promise<SubmitAnswerResponse> => ({
  status: 'success',
  question_id: 101,
  grade_result: {
    is_correct: true,
    score: 4,
    full_score: 4,
    error_type: null,
    short_feedback: '完整写出了两个根，步骤清楚。',
    knowledge_tags: ['quadratics'],
    student_feedback: '这次你补上了完整解集。',
  },
  reference_answer: '\\(x = 3\\) or \\(x = -\\frac{1}{2}\\)',
  marking_points: ['factorise', 'state both roots'],
  source: { year: 2024, session: 's', paper: 1, variant: 2, question_number: '5' },
})

export function PracticeRecommendationsReplayPage() {
  return (
    <main className="min-h-screen bg-slate-100 px-4 py-6 text-slate-950">
      <div className="mx-auto max-w-6xl space-y-5">
        <header>
          <p className="text-xs font-semibold uppercase tracking-wide text-blue-700">Replay</p>
          <h1 className="mt-1 text-xl font-semibold">Practice Recommendations Replay</h1>
        </header>
        <PracticeRecommendations
          request={{ images: [], upload_intent: 'past_paper', paper_code: '9709/12/M/J/24' }}
          agentSteps={[]}
          summary={practiceReplaySummary}
          questions={practiceReplayQuestions}
          initialResponse={autoRecommendationFixture}
          loader={async () => autoRecommendationFixture}
          answerSubmitter={replayAnswerSubmitter}
        />
        <PracticeRecommendations
          request={{ images: [], upload_intent: 'custom_homework' }}
          agentSteps={[]}
          summary={practiceReplaySummary}
          questions={practiceReplayQuestions}
          initialResponse={askFirstRecommendationFixture}
          loader={async () => autoRecommendationFixture}
          answerSubmitter={replayAnswerSubmitter}
        />
        <PracticeRecommendations
          request={{ images: [], upload_intent: 'unknown' }}
          agentSteps={[]}
          summary={practiceReplaySummary}
          questions={practiceReplayQuestions}
          initialResponse={unavailableRecommendationFixture}
          loader={async () => unavailableRecommendationFixture}
        />
      </div>
    </main>
  )
}
