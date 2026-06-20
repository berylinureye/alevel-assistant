import { useState } from 'react'
import { QuestionCard } from '../components/QuestionCard'
import { SkeletonQuestionCard } from '../components/SkeletonQuestionCard'
import { questionCardReplayFixture } from '../fixtures/questionCardReplay'

export function QuestionCardReplayPage() {
  const [expanded, setExpanded] = useState(true)

  return (
    <main className="min-h-screen bg-slate-100 px-4 py-8 text-slate-950">
      <div className="mx-auto max-w-4xl space-y-5">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
            Question Card Replay
          </p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">题目诊断卡预览</h1>
        </div>

        <SkeletonQuestionCard
          data={{
            question_number: 'Q3',
            question_text: questionCardReplayFixture.question_text,
            student_answer: questionCardReplayFixture.student_answer,
            working_steps: questionCardReplayFixture.working_steps,
            marks: questionCardReplayFixture.full_score,
            confidence: questionCardReplayFixture.confidence,
          }}
          agents={{
            'DeepSeek-Fast': {
              agent_name: 'DeepSeek-Fast',
              model_id: 'deepseek-chat',
              status: 'started',
            },
            'Qwen-Accurate': {
              agent_name: 'Qwen-Accurate',
              model_id: 'qwen-max',
              status: 'completed',
            },
          }}
        />

        <QuestionCard
          question={questionCardReplayFixture}
          expanded={expanded}
          onToggleExpand={() => setExpanded((value) => !value)}
        />
      </div>
    </main>
  )
}
