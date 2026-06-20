import type { QuestionExtractedData } from '../api/client'
import { renderMath } from '../utils/mathRender'
import { getAgentDisplay, getAgentSortOrder } from '../utils/modelDisplay'

export interface AgentRunState {
  agent_name: string
  model_id?: string
  status: string
}

export interface SkeletonQuestionCardProps {
  data: QuestionExtractedData
  /** 该题当前各 agent 的运行状态（键为 agent_name） */
  agents: Record<string, AgentRunState>
  /** 本题对应的上传页预览（object URL）—— 骨架阶段暂不展示缩略图，保留接口一致性 */
  imageUrl?: string
}

const GRADING_AGENT_NAMES = [
  'DeepSeek-Fast',
  'Qwen-Fast',
  'GLM-Fast',
  'Qwen-Accurate',
  'GLM-Thinking',
]

const STATUS_LABEL: Record<string, string> = {
  started: '批改中',
  completed: '已完成',
  voting: '投票中',
  timeout: '超时',
  failed: '失败',
}

function statusDotClass(status: string): string {
  if (status === 'completed') return 'bg-emerald-400'
  if (status === 'timeout' || status === 'failed') return 'bg-red-400'
  if (status === 'voting') return 'bg-violet-400 animate-pulse'
  return 'bg-blue-400 animate-pulse'
}

export function SkeletonQuestionCard({ data, agents }: SkeletonQuestionCardProps) {
  const questionText = typeof data.question_text === 'string' ? data.question_text : ''
  const studentAnswer = typeof data.student_answer === 'string' ? data.student_answer : ''
  const hasAnswer = studentAnswer.trim().length > 0
  const workingSteps = data.working_steps ?? []
  const agentEntries = Object.values(agents).sort((a, b) => {
    const na = getAgentSortOrder(a.agent_name)
    const nb = getAgentSortOrder(b.agent_name)
    return na - nb
  })

  return (
    <article className="animate-[fadeIn_0.3s_ease-out] relative overflow-visible rounded-lg border border-slate-200 bg-white shadow-sm border-l-4 border-l-blue-300">
      <div className="flex items-start justify-between gap-3 border-b border-slate-100 p-4">
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
          <h3 className="text-lg font-semibold text-slate-950">{data.question_number}</h3>
          <span className="inline-flex items-center gap-1.5 rounded-md bg-blue-50 px-2.5 py-0.5 text-xs font-semibold text-blue-700">
            <span className="h-1.5 w-1.5 rounded-full bg-blue-500 animate-pulse" aria-hidden />
            AI 判断中
          </span>
          {typeof data.marks === 'number' && data.marks > 0 ? (
            <span className="text-xs text-slate-500">{data.marks} 分</span>
          ) : null}
        </div>
      </div>

      <div className="space-y-4 p-4">
        {questionText ? (
          <div>
            <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
              题目
            </div>
            <div
              className="whitespace-pre-wrap break-words text-sm text-slate-800"
              dangerouslySetInnerHTML={{ __html: renderMath(questionText) }}
            />
          </div>
        ) : null}

        <div>
          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
            学生答案
          </div>
          {hasAnswer ? (
            <div
              className="whitespace-pre-wrap break-words rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-800"
              dangerouslySetInnerHTML={{ __html: renderMath(studentAnswer) }}
            />
          ) : (
            <div className="rounded-md bg-slate-50 px-3 py-2 text-sm italic text-slate-400">
              （未作答）
            </div>
          )}
        </div>

        {workingSteps.length > 0 ? (
          <div>
            <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
              解题步骤
            </div>
            <ol className="list-decimal space-y-0.5 pl-5 text-sm text-slate-700">
              {workingSteps.map((s, i) => (
                <li
                  key={i}
                  className="whitespace-pre-wrap break-words"
                  dangerouslySetInnerHTML={{ __html: renderMath(typeof s === 'string' ? s : String(s ?? '')) }}
                />
              ))}
            </ol>
          </div>
        ) : null}

        <div className="rounded-md border border-dashed border-blue-200 bg-blue-50/40 px-3 py-2">
          <div className="mb-1.5 flex items-center gap-2 text-xs text-slate-700">
            <span className="relative flex h-2 w-2" aria-hidden>
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-60" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-blue-500" />
            </span>
            <span>多轮 AI 批改与复核中…</span>
          </div>
          <ul className="grid min-w-0 grid-cols-1 gap-1.5 sm:flex sm:flex-wrap">
            {GRADING_AGENT_NAMES.map((name) => {
              const entry = agentEntries.find((e) => e.agent_name === name)
              const status = entry?.status ?? 'pending'
              const label = STATUS_LABEL[status] ?? (status === 'pending' ? '排队中' : status)
              const display = getAgentDisplay(name)
              return (
                <li
                  key={name}
                  className="inline-flex min-w-0 items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2 py-0.5 text-[11px] text-slate-700"
                  title={display.description}
                >
                  <span className={`h-1.5 w-1.5 rounded-full ${statusDotClass(status)}`} aria-hidden />
                  <span className="shrink-0 font-medium">{display.shortName}</span>
                  <span className="text-slate-400">·</span>
                  <span className="min-w-0 truncate">{display.roleName}</span>
                  <span className="text-slate-400">·</span>
                  <span className={`shrink-0 ${
                    status === 'completed' ? 'text-emerald-600'
                    : status === 'failed' || status === 'timeout' ? 'text-red-500'
                    : status === 'pending' ? 'text-slate-400'
                    : 'text-blue-600'
                  }`}>{label}</span>
                </li>
              )
            })}
          </ul>
        </div>
      </div>
    </article>
  )
}
