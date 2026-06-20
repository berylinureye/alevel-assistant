import { useEffect, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import { chatQuestion, chatQuestionStream, trackEvent } from '../api/client'
import type { ChatMessage, ExplainLevel, QuestionResult } from '../types'
import { renderMath } from '../utils/mathRender'

interface ChatPanelProps {
  question: QuestionResult
  solutionContext: string
}

type PanelMessage = ChatMessage & { acknowledged?: boolean }

const LEVEL_BADGE: Record<ExplainLevel, { label: string; tone: string } | null> = {
  1: null,
  2: { label: '换种讲法', tone: 'bg-amber-100 text-amber-700' },
  3: { label: '回退补基础', tone: 'bg-rose-100 text-rose-700' },
}

// 每个层级推到下一层时，前端自动注入的"提示文字"——让学生的再问具象一点
const FOLLOWUP_BY_LEVEL: Record<ExplainLevel, string> = {
  1: '能再换个角度讲一遍吗？这一版没太懂。',
  2: '还是没跟上，能不能换更简单的数字或者倒着讲？',
  3: '我可能基础就没打好，能从更基本的前置概念开始讲吗？',
}

export function ChatPanel({ question, solutionContext }: ChatPanelProps) {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<PanelMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  // 递进层级：1 拆细 → 2 换讲法 → 3 回退前置
  // 点"换个方式"+1 并锁定到下次追问；点"听懂了"重置到 1
  const [level, setLevel] = useState<ExplainLevel>(1)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // 记录当前流式请求的 cancel 句柄，用于组件卸载或被覆盖时中断
  const cancelRef = useRef<(() => void) | null>(null)

  useEffect(() => () => {
    cancelRef.current?.()
  }, [])

  const callChat = (newMessage: string, levelOverride?: ExplainLevel) => {
    const effectiveLevel = levelOverride ?? level
    // 先占位一条 assistant 消息，让用户看到"正在打字"
    setMessages((prev) => [...prev, { role: 'assistant', content: '' }])
    setLoading(true)

    // 快照当前会话（不含刚占位的空 assistant）
    const conversationSnapshot = messages.map((m) => ({ role: m.role, content: m.content }))

    return new Promise<void>((resolve) => {
      let finished = false
      let accumulated = ''

      // 更新最后一条 assistant 消息内容的工具
      const updateLast = (content: string, acknowledged?: boolean) => {
        setMessages((prev) => {
          if (prev.length === 0) return prev
          const copy = prev.slice()
          const lastIdx = copy.length - 1
          if (copy[lastIdx].role !== 'assistant') return prev
          copy[lastIdx] = {
            ...copy[lastIdx],
            content,
            ...(acknowledged !== undefined ? { acknowledged } : {}),
          }
          return copy
        })
      }

      // 先走流式；失败/中断时 fallback 到一次性接口
      const tryFallback = async (reason: string) => {
        try {
          const res = await chatQuestion({
            question_text: question.parent_stem
              ? `${question.parent_stem}\n\n${question.question_text}`
              : question.question_text,
            student_answer: question.student_answer,
            error_type: question.error_type,
            solution_context: solutionContext,
            conversation: conversationSnapshot,
            new_message: newMessage,
            explain_level: effectiveLevel,
          })
          updateLast(res.reply)
        } catch {
          updateLast(
            accumulated
              ? accumulated + `\n\n（网络中断：${reason}）`
              : '回复失败，请重试。',
            true,
          )
        } finally {
          setLoading(false)
          resolve()
        }
      }

      cancelRef.current = chatQuestionStream(
        {
          question_text: question.parent_stem
            ? `${question.parent_stem}\n\n${question.question_text}`
            : question.question_text,
          student_answer: question.student_answer,
          error_type: question.error_type,
          solution_context: solutionContext,
          conversation: conversationSnapshot,
          new_message: newMessage,
          explain_level: effectiveLevel,
        },
        {
          onChunk: (piece) => {
            accumulated += piece
            updateLast(accumulated)
          },
          onDone: (finalClean) => {
            finished = true
            // 用服务端清洗过的最终文本替换（LaTeX 清洗后更准）
            if (finalClean) updateLast(finalClean)
            setLoading(false)
            resolve()
          },
          onError: (msg) => {
            if (finished) return
            finished = true
            // 流失败但已经累计了一部分就保留；否则 fallback 一次性接口再试
            if (accumulated.length > 10) {
              updateLast(accumulated, true)
              setLoading(false)
              resolve()
            } else {
              void tryFallback(msg)
            }
          },
        },
      )
    })
  }

  const handleSend = async () => {
    const text = input.trim()
    if (!text || loading) return
    setMessages((prev) => [...prev, { role: 'user', content: text }])
    setInput('')
    trackEvent('ui_chat_send', { level, turn: messages.length, text_len: text.length })
    await callChat(text)
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void handleSend()
    }
  }

  // ✅ 听懂了：当前条按钮隐藏，层级回到 1（下次追问重新进入拆细模式）
  const handleGotIt = (idx: number) => {
    setMessages((prev) =>
      prev.map((m, i) => (i === idx ? { ...m, acknowledged: true } : m)),
    )
    trackEvent('ui_chat_got_it', { level, turn: messages.length })
    setLevel(1)
  }

  // 🔄 换个方式解释：层级 +1（封顶 3），自动续问，锁定后续追问层级
  const handleReexplain = async (idx: number) => {
    if (loading) return
    const nextLevel: ExplainLevel = (Math.min(3, level + 1) as ExplainLevel)
    setMessages((prev) =>
      prev.map((m, i) => (i === idx ? { ...m, acknowledged: true } : m)),
    )
    trackEvent('ui_chat_reexplain', { from_level: level, to_level: nextLevel, turn: messages.length })
    setLevel(nextLevel)
    const followUp = FOLLOWUP_BY_LEVEL[level] // 用当前层级对应的提示文案
    setMessages((prev) => [...prev, { role: 'user', content: followUp }])
    await callChat(followUp, nextLevel)
  }

  // 只在最新 assistant 条上显示按钮
  const lastAssistantIdx = (() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'assistant') return i
    }
    return -1
  })()

  const badge = LEVEL_BADGE[level]

  return (
    <div className="border-b border-gray-100">
      <button
        type="button"
        onClick={() => {
          setOpen((v) => {
            const next = !v
            if (next) trackEvent('ui_chat_open', { error_type: question.error_type })
            return next
          })
        }}
        className="flex w-full items-center gap-2 px-4 py-3 text-left text-sm font-medium text-emerald-700 transition hover:bg-emerald-50/50"
      >
        <span className="text-base">💬</span>
        <span>{open ? '收起 AI 问答' : '还有疑问？问问 AI 老师'}</span>
        {badge ? (
          <span className={`ml-2 rounded-full px-2 py-0.5 text-[10px] font-normal ${badge.tone}`}>
            {badge.label}
          </span>
        ) : null}
        <span className={`ml-auto text-gray-400 transition-transform ${open ? 'rotate-180' : ''}`}>▼</span>
      </button>

      {open ? (
        <div className="px-4 pb-4">
          <div className="mb-3 max-h-96 space-y-3 overflow-y-auto rounded-lg bg-gray-50 p-3">
            {messages.length === 0 ? (
              <p className="py-4 text-center text-xs text-gray-400">
                输入你的问题，AI 老师会用中文为你解答
              </p>
            ) : (
              messages.map((msg, i) => {
                const isUser = msg.role === 'user'
                const showButtons =
                  !isUser && i === lastAssistantIdx && !msg.acknowledged && !loading
                // 下一档按钮文字：给学生预期
                const reexplainLabel =
                  level === 1 ? '🔄 换个方式解释' : level === 2 ? '🧩 再换一种说法' : '⬅️ 从基础开始再讲'
                return (
                  <div key={i} className={`flex flex-col ${isUser ? 'items-end' : 'items-start'}`}>
                    <div
                      className={`max-w-[90%] rounded-xl px-3 py-2 text-sm whitespace-pre-wrap [&_.katex]:text-inherit ${
                        isUser
                          ? 'bg-emerald-600 text-white'
                          : 'border border-gray-200 bg-white text-gray-800 shadow-sm'
                      }`}
                      dangerouslySetInnerHTML={{
                        __html: isUser
                          ? msg.content.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                          : renderMath(msg.content),
                      }}
                    />
                    {showButtons ? (
                      <div className="mt-2 flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => handleGotIt(i)}
                          className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700 transition hover:bg-emerald-100"
                        >
                          ✅ 听懂了
                        </button>
                        {level < 3 ? (
                          <button
                            type="button"
                            onClick={() => void handleReexplain(i)}
                            className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700 transition hover:bg-amber-100"
                          >
                            {reexplainLabel}
                          </button>
                        ) : (
                          // 已经到第 3 层，不再递增，换成"再试一次从基础讲"
                          <button
                            type="button"
                            onClick={() => void handleReexplain(i)}
                            className="rounded-full border border-rose-200 bg-rose-50 px-3 py-1 text-xs font-medium text-rose-700 transition hover:bg-rose-100"
                          >
                            ⬅️ 再回退一步讲
                          </button>
                        )}
                      </div>
                    ) : null}
                  </div>
                )
              })
            )}
            {loading ? (
              <div className="flex justify-start">
                <div className="flex items-center gap-1.5 rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-gray-500 shadow-sm">
                  <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-gray-300 border-t-gray-600" />
                  思考中…
                </div>
              </div>
            ) : null}
            <div ref={messagesEndRef} />
          </div>

          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入你的问题…"
              disabled={loading}
              className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 disabled:bg-gray-100"
            />
            <button
              type="button"
              onClick={() => void handleSend()}
              disabled={loading || !input.trim()}
              className="rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              发送
            </button>
          </div>
        </div>
      ) : null}
    </div>
  )
}
