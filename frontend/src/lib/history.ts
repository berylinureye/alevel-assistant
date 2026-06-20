import type { PageSummary, QuestionResult } from '../types'

const STORAGE_KEY = 'alevel-ta-history-v1'
const MAX_RECORDS = 200

export interface HistoryRecord {
  id: string
  timestamp: number
  questions: QuestionResult[]
  summary: PageSummary | null
}

function safeParse(raw: string | null): HistoryRecord[] {
  if (!raw) return []
  try {
    const data = JSON.parse(raw)
    if (!Array.isArray(data)) return []
    return data.filter((r) => r && typeof r.id === 'string' && typeof r.timestamp === 'number')
  } catch {
    return []
  }
}

export function loadHistory(): HistoryRecord[] {
  if (typeof localStorage === 'undefined') return []
  return safeParse(localStorage.getItem(STORAGE_KEY)).sort(
    (a, b) => b.timestamp - a.timestamp,
  )
}

export function saveRecord(record: Omit<HistoryRecord, 'id' | 'timestamp'>): HistoryRecord {
  const entry: HistoryRecord = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    timestamp: Date.now(),
    ...record,
  }
  const all = [entry, ...loadHistory()].slice(0, MAX_RECORDS)
  localStorage.setItem(STORAGE_KEY, JSON.stringify(all))
  return entry
}

export function deleteRecord(id: string): HistoryRecord[] {
  const all = loadHistory().filter((r) => r.id !== id)
  localStorage.setItem(STORAGE_KEY, JSON.stringify(all))
  return all
}

export function clearHistory(): void {
  localStorage.removeItem(STORAGE_KEY)
}

export interface KnowledgeAggregate {
  tag: string
  wrongCount: number
  totalCount: number
}

/** subtopic key → 所属 paper/chapter 的映射 */
export interface SubtopicChapter {
  paper_num: number
  topic_name: string
  topic_name_cn: string
}
export type SubtopicChapterMap = Record<string, SubtopicChapter>

/** 汇总所有记录中错题的知识点分布，按 paper → 章节分组。
 *  传入 `chapterMap` 时，同一章节的所有 subtopic（例如 variance/standard_deviation）
 *  会合并成一个条目；找不到映射的标签以原标签单独展示。 */
export function aggregateKnowledgePoints(
  records: HistoryRecord[],
  chapterMap?: SubtopicChapterMap,
): KnowledgeAggregate[] {
  const wrong = new Map<string, number>()
  const total = new Map<string, number>()

  const resolve = (rawTag: string): string => {
    if (!chapterMap) return rawTag
    const hit = chapterMap[rawTag]
    if (!hit) return rawTag
    return `Paper ${hit.paper_num} · ${hit.topic_name}`
  }

  for (const r of records) {
    for (const q of r.questions) {
      const tags = q.knowledge_tags ?? []
      const grouped = new Set<string>()
      for (const t of tags) {
        const raw = (t || '').trim()
        if (!raw) continue
        grouped.add(resolve(raw))
      }
      for (const key of grouped) {
        total.set(key, (total.get(key) ?? 0) + 1)
        if (!q.is_correct && !q.unanswered) {
          wrong.set(key, (wrong.get(key) ?? 0) + 1)
        }
      }
    }
  }
  const keys = new Set<string>([...wrong.keys(), ...total.keys()])
  return [...keys]
    .map((tag) => ({
      tag,
      wrongCount: wrong.get(tag) ?? 0,
      totalCount: total.get(tag) ?? 0,
    }))
    .sort((a, b) => b.wrongCount - a.wrongCount || b.totalCount - a.totalCount)
}

export interface AccuracyPoint {
  timestamp: number
  correct: number
  total: number
  accuracy: number
}

/** 按日聚合正确率（同一天的多次批改合并成一个数据点），时间升序 */
export function computeAccuracySeries(records: HistoryRecord[]): AccuracyPoint[] {
  const dayKey = (ts: number) => {
    const d = new Date(ts)
    return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
  }
  const bucket = new Map<number, { correct: number; total: number }>()
  for (const r of records) {
    const key = dayKey(r.timestamp)
    let acc = bucket.get(key)
    if (!acc) {
      acc = { correct: 0, total: 0 }
      bucket.set(key, acc)
    }
    for (const q of r.questions) {
      if (q.unanswered) continue
      acc.total += 1
      if (q.is_correct) acc.correct += 1
    }
  }
  return [...bucket.entries()]
    .map(([timestamp, { correct, total }]) => ({
      timestamp,
      correct,
      total,
      accuracy: total > 0 ? correct / total : 0,
    }))
    .filter((p) => p.total > 0)
    .sort((a, b) => a.timestamp - b.timestamp)
}
