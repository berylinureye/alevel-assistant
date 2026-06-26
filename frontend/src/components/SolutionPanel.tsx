import { useEffect, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import { chatQuestion, explainQuestion, trackEvent } from '../api/client'
import type { ChatMessage, QuestionResult } from '../types'
import { renderMath } from '../utils/mathRender'

const FORBIDDEN_SOLUTION_PATTERNS = [
  /学生(?:的)?作答[:：]/,
  /学生答案[:：]/,
  /正确答案[:：]/,
  /批改反馈[:：]/,
  /重要[:：]\s*正确答案/,
  /先确认解题路径/,
  /如果你计算出的结果和正确答案不一致/,
  /绝对不要输出/,
]

function hasForbiddenSolutionStyle(text: string | null | undefined): boolean {
  if (!text) return false
  return FORBIDDEN_SOLUTION_PATTERNS.some((pattern) => pattern.test(text))
}

interface SolutionPanelProps {
  question: QuestionResult
}

export function SolutionPanel({ question }: SolutionPanelProps) {
  const [open, setOpen] = useState(false)
  // 优先使用预生成的缓存，没有时才按需请求
  const [explanation, setExplanation] = useState<string | null>(
    question.solution_text &&
    !hasForbiddenSolutionStyle(question.solution_text)
      ? question.solution_text
      : null,
  )
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // 追问对话
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // 如果 question.solution_text 变化（比如流式更新），同步
  useEffect(() => {
    if (
      question.solution_text &&
      !explanation &&
      !hasForbiddenSolutionStyle(question.solution_text)
    ) {
      setExplanation(question.solution_text)
    }
  }, [explanation, question.solution_text])

  const handleToggle = async () => {
    if (open) {
      setOpen(false)
      return
    }
    setOpen(true)
    trackEvent('ui_solution_expand', {
      cached: explanation != null,
      is_correct: question.is_correct,
      error_type: question.error_type,
    })

    // 已有缓存内容，直接展示
    if (explanation != null) return

    // 没有缓存，按需请求（降级）
    setLoading(true)
    setError(null)
    try {
      const res = await explainQuestion({
        question_text: question.parent_stem
          ? `${question.parent_stem}\n\n${question.question_text}`
          : question.question_text,
        student_answer: question.student_answer,
        working_steps: question.working_steps,
        is_correct: question.is_correct,
        error_type: question.error_type,
        score: question.score,
        full_score: question.full_score,
        correct_answer: question.correct_answer,
      })
      if (hasForbiddenSolutionStyle(res.solution_explanation)) {
        throw new Error('解题思路格式不符合要求，已拦截，请重试')
      }
      setExplanation(res.solution_explanation)
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取解题思路失败')
    } finally {
      setLoading(false)
    }
  }

  const handleChatSend = async () => {
    const text = chatInput.trim()
    if (!text || chatLoading) return

    const userMsg: ChatMessage = { role: 'user', content: text }
    setMessages((prev) => [...prev, userMsg])
    setChatInput('')
    setChatLoading(true)

    try {
      const res = await chatQuestion({
        question_text: question.parent_stem
          ? `${question.parent_stem}\n\n${question.question_text}`
          : question.question_text,
        student_answer: question.student_answer,
        error_type: question.error_type,
        solution_context: explanation ?? '',
        conversation: messages,
        new_message: text,
      })
      const assistantMsg: ChatMessage = { role: 'assistant', content: res.reply }
      setMessages((prev) => [...prev, assistantMsg])
    } catch {
      const errorMsg: ChatMessage = { role: 'assistant', content: '回复失败，请重试。' }
      setMessages((prev) => [...prev, errorMsg])
    } finally {
      setChatLoading(false)
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void handleChatSend()
    }
  }

  return (
    <div className="border-b border-gray-100">
      <button
        type="button"
        onClick={() => void handleToggle()}
        className="flex w-full items-center gap-2 px-4 py-3 text-left text-sm font-medium text-indigo-700 transition hover:bg-indigo-50/50"
      >
        <span className="text-base">📖</span>
        <span>{open ? '收起解题思路' : '查看解题思路'}</span>
        {loading ? (
          <span className="ml-auto h-4 w-4 animate-spin rounded-full border-2 border-indigo-300 border-t-indigo-600" />
        ) : (
          <span className={`ml-auto text-gray-400 transition-transform ${open ? 'rotate-180' : ''}`}>▼</span>
        )}
      </button>

      {open ? (
        <div className="px-4 pb-4">
          {/* 解题思路内容 */}
          {loading && explanation == null ? (
            <div className="flex items-center gap-2 py-4 text-sm text-gray-500">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-gray-300 border-t-gray-600" />
              正在生成解题思路…
            </div>
          ) : error != null ? (
            <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
          ) : explanation != null ? (
            <>
              <div
                className="max-w-full text-sm leading-relaxed whitespace-pre-wrap text-gray-800 overflow-x-auto [overflow-wrap:anywhere] [&_.katex]:text-inherit [&_.katex-display]:my-1 [&_.katex-display]:overflow-x-auto"
                dangerouslySetInnerHTML={{ __html: renderMath(explanation) }}
              />

              {/* 追问对话区域 */}
              <div className="mt-4 border-t border-gray-100 pt-3">
                <p className="mb-2 text-xs font-medium text-gray-500">还有疑问？继续问 AI 老师</p>

                {messages.length > 0 ? (
                  <div className="mb-3 max-h-72 space-y-2.5 overflow-y-auto rounded-lg bg-gray-50 p-3">
                    {messages.map((msg, i) => (
                      <div
                        key={i}
                        className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                      >
                        <div
                          className={`max-w-[90%] rounded-xl px-3 py-2 text-sm whitespace-pre-wrap [&_.katex]:text-inherit ${
                            msg.role === 'user'
                              ? 'bg-indigo-600 text-white'
                              : 'border border-gray-200 bg-white text-gray-800 shadow-sm'
                          }`}
                          dangerouslySetInnerHTML={{
                            __html:
                              msg.role === 'assistant'
                                ? renderMath(msg.content)
                                : msg.content.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'),
                          }}
                        />
                      </div>
                    ))}
                    {chatLoading ? (
                      <div className="flex justify-start">
                        <div className="flex items-center gap-1.5 rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-gray-500 shadow-sm">
                          <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-gray-300 border-t-gray-600" />
                          思考中…
                        </div>
                      </div>
                    ) : null}
                    <div ref={messagesEndRef} />
                  </div>
                ) : null}

                <div className="flex gap-2">
                  <input
                    type="text"
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="输入你的问题…"
                    disabled={chatLoading}
                    className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:bg-gray-100"
                  />
                  <button
                    type="button"
                    onClick={() => void handleChatSend()}
                    disabled={chatLoading || !chatInput.trim()}
                    className="rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    发送
                  </button>
                </div>
              </div>
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
