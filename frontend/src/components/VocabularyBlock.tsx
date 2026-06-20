import { useMemo } from 'react'
import { MATH_VOCABULARY, type VocabEntry } from '../constants/mathVocabulary'

interface VocabularyBlockProps {
  questionText: string
  /** 题目中文翻译（由后端提供时传入） */
  questionTextZh?: string
}

function matchTerms(text: string): VocabEntry[] {
  const lower = text.toLowerCase()
  const matched: VocabEntry[] = []

  const sorted = [...MATH_VOCABULARY].sort((a, b) => b.term.length - a.term.length)

  for (const entry of sorted) {
    const termLower = entry.term.toLowerCase()
    const re = new RegExp(`\\b${escapeRegex(termLower)}\\b`, 'i')
    if (re.test(lower)) {
      matched.push(entry)
    }
  }

  return matched
}

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

export function VocabularyBlock({ questionText, questionTextZh }: VocabularyBlockProps) {
  const terms = useMemo(() => matchTerms(questionText), [questionText])

  if (terms.length === 0) return null

  return (
    <div className="border-b border-gray-100 px-4 py-3">
      <h4 className="mb-2 text-xs font-medium tracking-wide text-gray-500">重点词汇</h4>
      <div className="flex flex-wrap gap-1.5">
        {terms.map((entry) => (
          <span
            key={entry.term}
            className="inline-flex items-center gap-1 rounded-md border border-indigo-100 bg-indigo-50/60 px-2 py-0.5 text-xs"
          >
            <span className="font-medium text-indigo-800">{entry.term}</span>
            <span className="text-indigo-500">→</span>
            <span className="text-indigo-700">{entry.chinese}</span>
          </span>
        ))}
      </div>
      {questionTextZh != null && questionTextZh !== '' ? (
        <div className="mt-2.5 rounded-md bg-gray-50 px-3 py-2">
          <p className="text-xs leading-relaxed text-gray-700">
            <span className="mr-1 font-medium text-gray-500">题目翻译：</span>
            {questionTextZh}
          </p>
        </div>
      ) : null}
    </div>
  )
}
