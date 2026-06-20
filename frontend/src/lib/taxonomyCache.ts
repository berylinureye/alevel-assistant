/**
 * 进程内 taxonomy 缓存：避免每张 QuestionCard 都请求一次 /questions/meta/taxonomy。
 * 首次调用时 fetch，后续所有订阅方直接复用。
 */
import { fetchTaxonomy } from '../api/practice'
import type { SubtopicChapterMap } from './history'

let cached: SubtopicChapterMap | null = null
let inflight: Promise<SubtopicChapterMap> | null = null
const listeners = new Set<(m: SubtopicChapterMap) => void>()

function load(): Promise<SubtopicChapterMap> {
  if (cached) return Promise.resolve(cached)
  if (inflight) return inflight
  inflight = fetchTaxonomy()
    .then((resp) => {
      const map: SubtopicChapterMap = {}
      for (const paper of resp.papers) {
        for (const topic of paper.topics) {
          for (const sub of topic.subtopics) {
            map[sub] = {
              paper_num: paper.paper_num,
              topic_name: topic.name,
              topic_name_cn: topic.name_cn,
            }
          }
        }
      }
      cached = map
      for (const fn of listeners) fn(map)
      return map
    })
    .catch(() => {
      const empty: SubtopicChapterMap = {}
      cached = empty
      for (const fn of listeners) fn(empty)
      return empty
    })
    .finally(() => {
      inflight = null
    })
  return inflight
}

export function getTaxonomyMap(): SubtopicChapterMap | null {
  return cached
}

export function subscribeTaxonomy(fn: (m: SubtopicChapterMap) => void): () => void {
  if (cached) fn(cached)
  listeners.add(fn)
  void load()
  return () => {
    listeners.delete(fn)
  }
}

/** 把一组 raw tags（subtopic 名）解析为 "Paper X · 章节" 的唯一列表 */
export function resolveChapters(tags: string[], map: SubtopicChapterMap | null): string[] {
  if (!map) return []
  const out = new Set<string>()
  for (const t of tags) {
    const raw = (t || '').trim()
    if (!raw) continue
    const hit = map[raw]
    if (hit) out.add(`Paper ${hit.paper_num} · ${hit.topic_name}`)
  }
  return [...out]
}
