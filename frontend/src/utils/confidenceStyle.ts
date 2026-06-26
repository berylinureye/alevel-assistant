/** confidence ∈ [0,1]（或批改置信度），返回 Tailwind 文字颜色类 */
export function confidenceTextClass(confidence: number): string {
  const p = Math.round(Math.min(1, Math.max(0, confidence)) * 100)
  if (p >= 80) return 'text-slate-950'
  if (p >= 50) return 'text-slate-700'
  return 'text-slate-500'
}

/** 显示为「85%」 */
export function confidencePercentRounded(confidence: number): number {
  return Math.round(Math.min(1, Math.max(0, confidence)) * 100)
}
