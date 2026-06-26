import { useState } from 'react'

const VALID_CODES = ['ALEVEL2026', 'BETA2026']

export function InviteGate({ onVerified }: { onVerified: () => void }) {
  const [code, setCode] = useState('')
  const [error, setError] = useState(false)
  const [shaking, setShaking] = useState(false)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (VALID_CODES.includes(code.trim().toUpperCase())) {
      localStorage.setItem('alevel-ta-invite-verified', 'true')
      onVerified()
    } else {
      setError(true)
      setShaking(true)
      setTimeout(() => setShaking(false), 500)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <form
        onSubmit={handleSubmit}
        className={`w-full max-w-sm space-y-4 rounded-xl border border-gray-200 bg-white p-8 shadow-sm ${shaking ? 'animate-shake' : ''}`}
      >
        <div className="text-center">
          <h1 className="text-xl font-bold text-gray-900">A-Level 作业助手</h1>
          <p className="mt-2 text-sm text-gray-500">内测阶段，请输入邀请码访问</p>
        </div>

        <input
          type="text"
          value={code}
          onChange={(e) => {
            setCode(e.target.value)
            setError(false)
          }}
          placeholder="请输入邀请码"
          className={`w-full rounded-lg border px-4 py-2.5 text-center text-sm outline-none transition ${
            error
              ? 'border-red-300 bg-red-50 text-red-700 placeholder-red-300'
              : 'border-gray-200 bg-gray-50 text-gray-900 placeholder-gray-400 focus:border-blue-400 focus:bg-white'
          }`}
          autoFocus
        />

        {error && (
          <p className="text-center text-xs text-red-500">邀请码无效，请重新输入</p>
        )}

        <button
          type="submit"
          className="w-full rounded-lg bg-blue-600 py-2.5 text-sm font-medium text-white transition hover:bg-blue-700 active:bg-blue-800"
        >
          进入
        </button>
      </form>
    </div>
  )
}
