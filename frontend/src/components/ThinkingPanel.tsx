import { useEffect, useRef, useState } from 'react'
import type { AgentStepData } from '../api/client'
import {
  buildAgentStepViewModels,
  type AgentStepBadge,
  type AgentStepStatusKind,
  type AgentStepViewModel,
} from './agentStepViewModel'

const COMPLETE_LINE = '分析完成'

function formatElapsed(sec: number): string {
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

export interface ThinkingPanelProps {
  isLoading: boolean
  onDismiss: () => void
  /** 多图时，例如「正在分析第 2/5 张图片…」 */
  progressHint?: string | null
  /** 流式追加的思考日志（如分割完成、识别题量） */
  logLines?: string[]
  /** 结构化 agent 执行轨迹 */
  agentSteps?: AgentStepData[]
  /** 当前进度，如「已完成 2/5 道题…」 */
  progressDetail?: string | null
  /** segmentation 累计的预计题量 */
  totalExpected?: number
  /** 所有题已批改完成（解题思路可能仍在后台生成）— 此时冻结计时 */
  gradingDone?: boolean
}

export function ThinkingPanel({
  isLoading,
  onDismiss,
  progressHint,
  logLines = [],
  agentSteps = [],
  progressDetail,
  totalExpected = 0,
  gradingDone = false,
}: ThinkingPanelProps) {
  const [phase, setPhase] = useState<'thinking' | 'completing'>('thinking')
  const [footerLabel, setFooterLabel] = useState('已用时 0:00')
  const [showCompleteLine, setShowCompleteLine] = useState(false)

  const startRef = useRef<number>(0)
  const intervalsRef = useRef<ReturnType<typeof setInterval>[]>([])
  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([])
  const completionHandledRef = useRef(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!isLoading) return

    for (const i of intervalsRef.current) {
      clearInterval(i)
    }
    intervalsRef.current = []

    let cancelled = false
    queueMicrotask(() => {
      if (cancelled) return

      completionHandledRef.current = false
      setPhase('thinking')
      setShowCompleteLine(false)
      startRef.current = Date.now()
      setFooterLabel('已用时 0:00')

      const tickElapsed = () => {
        const sec = Math.floor((Date.now() - startRef.current) / 1000)
        setFooterLabel(`已用时 ${formatElapsed(sec)}`)
      }
      tickElapsed()
      const elapsedId = setInterval(tickElapsed, 1000)
      intervalsRef.current.push(elapsedId)
    })

    return () => {
      cancelled = true
      for (const i of intervalsRef.current) {
        clearInterval(i)
      }
      intervalsRef.current = []
    }
  }, [isLoading])

  useEffect(() => {
    if (isLoading) return
    if (completionHandledRef.current) return

    completionHandledRef.current = true
    for (const i of intervalsRef.current) {
      clearInterval(i)
    }
    intervalsRef.current = []

    const finalSec = Math.floor((Date.now() - startRef.current) / 1000)
    setFooterLabel(`分析完成，用时 ${formatElapsed(finalSec)}`)
    setPhase('completing')
    setShowCompleteLine(true)
  }, [isLoading])

  // 批改完成（但 pipeline 可能仍在跑解题思路）— 冻结计时并关闭面板
  useEffect(() => {
    if (!gradingDone) return
    for (const i of intervalsRef.current) {
      clearInterval(i)
    }
    intervalsRef.current = []
    const finalSec = Math.floor((Date.now() - startRef.current) / 1000)
    setFooterLabel(`批改完成，用时 ${formatElapsed(finalSec)}`)
    const id = setTimeout(() => {
      onDismiss()
    }, 200)
    timersRef.current.push(id)
    return () => {
      clearTimeout(id)
      timersRef.current = timersRef.current.filter((t) => t !== id)
    }
  }, [gradingDone, onDismiss])

  useEffect(() => {
    if (phase !== 'completing' || isLoading) return
    if (!showCompleteLine) return

    const id = setTimeout(() => {
      onDismiss()
    }, 200)
    timersRef.current.push(id)

    return () => {
      clearTimeout(id)
      timersRef.current = timersRef.current.filter((t) => t !== id)
    }
  }, [phase, isLoading, showCompleteLine, onDismiss])

  useEffect(() => {
    const el = scrollRef.current
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  }, [logLines, showCompleteLine, progressDetail])

  const displayLines = [...logLines, ...(showCompleteLine ? [COMPLETE_LINE] : [])]
  const visibleSteps = buildAgentStepViewModels(agentSteps).slice(-80)
  const hasSteps = visibleSteps.length > 0
  const completedSteps = visibleSteps.filter((step) => step.status === 'completed').length
  const runningSteps = visibleSteps.filter((step) => step.status === 'running').length

  return (
    <div
      className="relative overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm"
      role="status"
      aria-live="polite"
    >
      <div className="border-b border-slate-100 px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-slate-950">
              {phase === 'thinking' && !gradingDone ? '批改路径与反馈生成中' : '批改完成'}
            </h3>
            <p className="mt-0.5 text-xs text-slate-500">{footerLabel}</p>
          </div>
          {hasSteps ? (
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5">
                {completedSteps}/{visibleSteps.length} 步完成
              </span>
              {runningSteps > 0 ? (
                <span className="rounded-full border border-blue-200 bg-blue-50 px-2 py-0.5 text-blue-700">
                  {runningSteps} 步运行中
                </span>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>

      <div className="px-4 py-4">
        {progressHint != null && progressHint !== '' && isLoading && phase === 'thinking' ? (
          <p className="mb-2 text-xs font-medium text-blue-700">{progressHint}</p>
        ) : null}

        {totalExpected > 0 && isLoading && phase === 'thinking' ? (
          <p className="mb-1 text-xs text-slate-500">本批约 {totalExpected} 道题</p>
        ) : null}

        {progressDetail != null && progressDetail !== '' && isLoading && phase === 'thinking' ? (
          <p className="mb-2 text-xs font-medium text-slate-700">{progressDetail}</p>
        ) : null}

        <div
          ref={scrollRef}
          className="max-h-[min(360px,45vh)] sm:max-h-[min(380px,50vh)] overflow-y-auto pr-1"
        >
          {hasSteps ? (
            <ol className="space-y-2.5">
              {visibleSteps.map((step, idx) => (
                <AgentStepItem
                  key={`${idx}-${step.questionNumber}-${step.title}-${step.status}`}
                  step={step}
                />
              ))}
              {showCompleteLine ? (
                <li className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-800">
                  {COMPLETE_LINE}
                </li>
              ) : null}
            </ol>
          ) : (
            <div className="space-y-2 text-sm leading-relaxed text-slate-700">
              {displayLines.map((line, idx) => (
                <p key={`${idx}-${line.slice(0, 24)}`} className="whitespace-pre-wrap break-words">
                  {line}
                </p>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function statusClass(status: AgentStepStatusKind): string {
  if (status === 'completed') return 'border-emerald-200 bg-emerald-50 text-emerald-700'
  if (status === 'failed') return 'border-red-200 bg-red-50 text-red-700'
  return 'border-blue-200 bg-blue-50 text-blue-700'
}

function dotClass(status: AgentStepStatusKind): string {
  if (status === 'completed') return 'bg-emerald-500'
  if (status === 'failed') return 'bg-red-500'
  return 'bg-blue-500 animate-pulse'
}

function badgeClass(badge: AgentStepBadge): string {
  if (badge.tone === 'success') return 'bg-emerald-50 text-emerald-700 ring-emerald-200'
  if (badge.tone === 'warning') return 'bg-amber-50 text-amber-700 ring-amber-200'
  if (badge.tone === 'error') return 'bg-red-50 text-red-700 ring-red-200'
  return 'bg-white text-slate-500 ring-slate-200'
}

function AgentStepItem({ step }: { step: AgentStepViewModel }) {
  return (
    <li className="grid grid-cols-[1rem_minmax(0,1fr)] gap-2">
      <div className="flex justify-center pt-2">
        <span className={`h-2 w-2 rounded-full ${dotClass(step.status)}`} aria-hidden />
      </div>
      <div className="rounded-md border border-slate-200 bg-slate-50/70 px-3 py-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${statusClass(step.status)}`}>
            {step.phaseLabel}
          </span>
          <span className="text-xs font-medium text-slate-500">{step.questionNumber}</span>
          {step.agentName ? (
            <span className="max-w-full truncate text-xs text-slate-400">{step.agentName}</span>
          ) : null}
          {step.tool ? (
            <span className="rounded bg-white px-1.5 py-0.5 text-[11px] text-slate-500 ring-1 ring-slate-200">
              {step.tool}
            </span>
          ) : null}
          {step.badges.map((badge) => (
            <span
              key={`${badge.label}-${badge.tone}`}
              className={`rounded px-1.5 py-0.5 text-[11px] ring-1 ${badgeClass(badge)}`}
            >
              {badge.label}
            </span>
          ))}
        </div>
        <p className="mt-1 text-sm font-medium text-slate-900">{step.title}</p>
        <p className="mt-0.5 whitespace-pre-wrap break-words text-xs leading-relaxed text-slate-600">
          {step.summary}
        </p>
        {step.fallbackReason ? (
          <p className="mt-1 rounded-md bg-amber-50 px-2 py-1 text-xs leading-relaxed text-amber-800 ring-1 ring-amber-100">
            已降级：{step.fallbackReason}
          </p>
        ) : null}
      </div>
    </li>
  )
}
