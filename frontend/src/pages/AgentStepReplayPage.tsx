import { ThinkingPanel } from '../components/ThinkingPanel'
import { agentStepReplayFixture } from '../fixtures/agentStepReplay'
import type { AgentStepData } from '../api/client'

export function AgentStepReplayPage() {
  return (
    <main className="min-h-screen bg-slate-100 px-4 py-8 text-slate-950">
      <div className="mx-auto max-w-3xl">
        <div className="mb-4">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
            Agent Step Replay
          </p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">真题批改流程预览</h1>
        </div>
        <ThinkingPanel
          isLoading
          onDismiss={() => undefined}
          progressHint="正在读取上传内容"
          progressDetail="已识别真题批改路径，正在准备题目级评分规则"
          totalExpected={4}
          agentSteps={agentStepReplayFixture as AgentStepData[]}
        />
      </div>
    </main>
  )
}
