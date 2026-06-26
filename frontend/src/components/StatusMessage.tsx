import { useCallback, useEffect, useState } from 'react'
import { ThinkingPanel } from './ThinkingPanel'
import type { AgentStepData } from '../api/client'

export interface StatusMessageProps {
  loading: boolean
  error: string | null
  infoMessage?: string | null
  /** 多图并行时当前启动的图片序号 */
  analysisProgress?: { current: number; total: number } | null
  thinkingLog?: string[]
  agentSteps?: AgentStepData[]
  progressDetail?: string | null
  /** segmentation 累计题量，用于思考面板提示 */
  totalExpected?: number
  dismissPanelVersion?: number
  /** 批改完成（无论解题思路是否还在后台生成），用来冻结计时 */
  gradingDone?: boolean
}

export function StatusMessage({
  loading,
  error,
  infoMessage,
  analysisProgress,
  thinkingLog,
  agentSteps = [],
  progressDetail,
  totalExpected = 0,
  dismissPanelVersion = 0,
  gradingDone = false,
}: StatusMessageProps) {
  const [panelVisible, setPanelVisible] = useState(false)

  useEffect(() => {
    if (!loading) return
    const timer = window.setTimeout(() => setPanelVisible(true), 0)
    return () => window.clearTimeout(timer)
  }, [loading])

  useEffect(() => {
    const timer = window.setTimeout(() => setPanelVisible(false), 0)
    return () => window.clearTimeout(timer)
  }, [dismissPanelVersion])

  const handleThinkingDismiss = useCallback(() => {
    setPanelVisible(false)
  }, [])

  if (error != null) {
    const isConnectionError = error.includes('无法连接到后端服务')
    return (
      <div
        role="alert"
        className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900 shadow-sm"
      >
        <p className="font-medium text-red-800">{error}</p>
        <p className="mt-2 text-xs text-red-700/90">
          {isConnectionError
            ? '请在项目根目录运行 python server.py 启动后端，再刷新页面重试。'
            : '提示：若已有部分题目结果，可向下滚动查看；开始新的分析后此提示将消失。'}
        </p>
      </div>
    )
  }

  if (infoMessage != null && infoMessage !== '') {
    return (
      <div
        role="status"
        className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 shadow-sm"
      >
        <p className="font-medium text-amber-800">{infoMessage}</p>
      </div>
    )
  }

  if (!loading && !panelVisible) {
    return null
  }

  const progressHint =
    loading &&
    analysisProgress != null &&
    analysisProgress.total > 1 &&
    analysisProgress.current > 0
      ? `正在分析第 ${analysisProgress.current}/${analysisProgress.total} 张图片…`
      : null

  return (
    <ThinkingPanel
      isLoading={loading}
      onDismiss={handleThinkingDismiss}
      progressHint={progressHint}
      logLines={thinkingLog}
      agentSteps={agentSteps}
      progressDetail={progressDetail}
      totalExpected={totalExpected}
      gradingDone={gradingDone}
    />
  )
}
