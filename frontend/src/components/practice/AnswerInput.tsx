import { useState } from 'react'

interface Props {
  onSubmit: (answer: string, steps: string[]) => void
  submitting: boolean
  disabled: boolean
}

export function AnswerInput({ onSubmit, submitting, disabled }: Props) {
  const [answer, setAnswer] = useState('')
  const [stepsText, setStepsText] = useState('')

  const handleSubmit = () => {
    if (!answer.trim()) return
    const steps = stepsText
      .split('\n')
      .map((s) => s.trim())
      .filter(Boolean)
    onSubmit(answer.trim(), steps)
  }

  return (
    <div className="space-y-3 border-t border-gray-100 pt-4">
      <div>
        <label className="mb-1 block text-sm font-medium text-gray-700">你的答案</label>
        <textarea
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          disabled={disabled}
          placeholder="输入最终答案，数学公式可用 LaTeX 格式 (如 3x^2 + 2)"
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400 disabled:bg-gray-50"
          rows={2}
        />
      </div>
      <div>
        <label className="mb-1 block text-sm font-medium text-gray-700">
          解题步骤 <span className="font-normal text-gray-400">(可选，每行一步)</span>
        </label>
        <textarea
          value={stepsText}
          onChange={(e) => setStepsText(e.target.value)}
          disabled={disabled}
          placeholder={"Step 1: ...\nStep 2: ..."}
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400 disabled:bg-gray-50"
          rows={3}
        />
      </div>
      <button
        type="button"
        onClick={handleSubmit}
        disabled={disabled || submitting || !answer.trim()}
        className="rounded-md bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {submitting ? '批改中...' : '提交答案'}
      </button>
    </div>
  )
}
