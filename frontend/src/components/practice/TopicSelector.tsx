import { useEffect, useState } from 'react'
import { fetchTaxonomy } from '../../api/practice'
import type { TaxonomyPaper, TaxonomySubtopic } from '../../api/practice'

interface Props {
  selected: string[]
  onChange: (topics: string[]) => void
}

export function TopicSelector({ selected, onChange }: Props) {
  const [papers, setPapers] = useState<TaxonomyPaper[]>([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [expandedTopics, setExpandedTopics] = useState<Set<string>>(new Set())

  useEffect(() => {
    fetchTaxonomy()
      .then((res) => setPapers(res.papers))
      .catch(() => setPapers([]))
      .finally(() => setLoading(false))
  }, [])

  const toggleExpand = (key: string) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }

  const toggleExpandTopic = (key: string) => {
    setExpandedTopics((prev) => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }

  const toggleTopic = (topicKey: string) => {
    onChange(
      selected.includes(topicKey)
        ? selected.filter((t) => t !== topicKey)
        : [...selected, topicKey],
    )
  }

  /** Select/deselect all subtopics under a chapter */
  const toggleChapter = (topic: TaxonomySubtopic) => {
    const keys = [topic.key, ...topic.subtopics]
    const allSelected = keys.every((k) => selected.includes(k))
    if (allSelected) {
      onChange(selected.filter((t) => !keys.includes(t)))
    } else {
      const merged = new Set([...selected, ...keys])
      onChange([...merged])
    }
  }

  /** Select/deselect all topics in a paper */
  const togglePaper = (paper: TaxonomyPaper) => {
    const allKeys = paper.topics.flatMap((t) => [t.key, ...t.subtopics])
    const allSelected = allKeys.every((k) => selected.includes(k))
    if (allSelected) {
      onChange(selected.filter((t) => !allKeys.includes(t)))
    } else {
      const merged = new Set([...selected, ...allKeys])
      onChange([...merged])
    }
  }

  const isPaperAllSelected = (paper: TaxonomyPaper): boolean => {
    const allKeys = paper.topics.flatMap((t) => [t.key, ...t.subtopics])
    return allKeys.length > 0 && allKeys.every((k) => selected.includes(k))
  }

  const isPaperPartialSelected = (paper: TaxonomyPaper): boolean => {
    const allKeys = paper.topics.flatMap((t) => [t.key, ...t.subtopics])
    return !isPaperAllSelected(paper) && allKeys.some((k) => selected.includes(k))
  }

  const isChapterAllSelected = (topic: TaxonomySubtopic): boolean => {
    const keys = [topic.key, ...topic.subtopics]
    return keys.every((k) => selected.includes(k))
  }

  const isChapterPartialSelected = (topic: TaxonomySubtopic): boolean => {
    const keys = [topic.key, ...topic.subtopics]
    return !isChapterAllSelected(topic) && keys.some((k) => selected.includes(k))
  }

  if (loading) {
    return <p className="text-sm text-gray-400">加载知识点分类...</p>
  }

  return (
    <div>
      <label className="mb-2 block text-sm font-medium text-gray-700">
        知识点筛选（按试卷 → 章节 → 细分知识点）
      </label>

      <div className="space-y-2">
        {papers.map((paper) => {
          const paperKey = `P${paper.paper_num}`
          const isExpanded = expanded.has(paperKey)
          const allSel = isPaperAllSelected(paper)
          const partialSel = isPaperPartialSelected(paper)

          return (
            <div key={paperKey} className="rounded-lg border border-gray-200 overflow-hidden">
              {/* Paper header */}
              <div className="flex items-center bg-gray-50">
                <button
                  type="button"
                  onClick={() => togglePaper(paper)}
                  className="flex items-center gap-2 px-3 py-2 text-sm"
                  title="全选/取消该试卷所有知识点"
                >
                  <Checkbox checked={allSel} partial={partialSel} />
                </button>

                <button
                  type="button"
                  onClick={() => toggleExpand(paperKey)}
                  className="flex flex-1 items-center justify-between py-2 pr-3 text-sm text-gray-700 hover:text-gray-900"
                >
                  <span>
                    <span className="font-medium">{paperKey}</span>
                    <span className="ml-1.5 text-gray-500">{paper.paper_name}</span>
                    <span className={`ml-2 inline-block rounded px-1.5 py-0.5 text-[10px] font-medium ${
                      paper.level === 'AS' ? 'bg-emerald-100 text-emerald-700' : 'bg-purple-100 text-purple-700'
                    }`}>
                      {paper.level}
                    </span>
                    <span className="ml-1.5 text-xs text-gray-400">
                      ({paper.topics.length} 章节, {paper.topics.reduce((s, t) => s + t.subtopics.length, 0)} 知识点)
                    </span>
                  </span>
                  <svg
                    className={`h-4 w-4 text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                    fill="none" viewBox="0 0 24 24" stroke="currentColor"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
              </div>

              {/* Expanded: chapters and subtopics */}
              {isExpanded && (
                <div className="border-t border-gray-100 bg-white">
                  {paper.topics.map((topic) => {
                    const chapterKey = `${paperKey}-${topic.key}`
                    const isTopicExpanded = expandedTopics.has(chapterKey)
                    const chapterAll = isChapterAllSelected(topic)
                    const chapterPartial = isChapterPartialSelected(topic)

                    return (
                      <div key={topic.key} className="border-b border-gray-50 last:border-b-0">
                        {/* Chapter header */}
                        <div className="flex items-center px-3 py-1.5 hover:bg-gray-50">
                          <button
                            type="button"
                            onClick={() => toggleChapter(topic)}
                            className="flex items-center gap-2 text-sm"
                            title="全选/取消该章节所有知识点"
                          >
                            <Checkbox checked={chapterAll} partial={chapterPartial} />
                          </button>

                          <button
                            type="button"
                            onClick={() => toggleExpandTopic(chapterKey)}
                            className="flex flex-1 items-center justify-between pl-2 py-1 text-sm"
                          >
                            <span>
                              <span className="text-gray-700 font-medium">{topic.name}</span>
                              <span className="ml-1.5 text-gray-400">{topic.name_cn}</span>
                              <span className="ml-1.5 text-xs text-gray-300">
                                ({topic.subtopics.length})
                              </span>
                            </span>
                            <svg
                              className={`h-3.5 w-3.5 text-gray-300 transition-transform ${isTopicExpanded ? 'rotate-180' : ''}`}
                              fill="none" viewBox="0 0 24 24" stroke="currentColor"
                            >
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                            </svg>
                          </button>
                        </div>

                        {/* Subtopics */}
                        {isTopicExpanded && (
                          <div className="flex flex-wrap gap-1.5 px-10 py-2 bg-gray-50/50">
                            {topic.subtopics.map((sub) => {
                              const active = selected.includes(sub)
                              return (
                                <button
                                  key={sub}
                                  type="button"
                                  onClick={() => toggleTopic(sub)}
                                  className={`rounded-full border px-2.5 py-0.5 text-xs transition ${
                                    active
                                      ? 'border-blue-500 bg-blue-50 text-blue-700'
                                      : 'border-gray-200 bg-white text-gray-500 hover:border-gray-300'
                                  }`}
                                >
                                  {sub.replace(/_/g, ' ')}
                                </button>
                              )
                            })}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {selected.length > 0 && (
        <button
          type="button"
          onClick={() => onChange([])}
          className="mt-2 text-xs text-gray-400 hover:text-gray-600"
        >
          清除所有选择 ({selected.length} 个知识点已选)
        </button>
      )}
    </div>
  )
}

/** Small checkbox indicator */
function Checkbox({ checked, partial }: { checked: boolean; partial: boolean }) {
  return (
    <span className={`inline-flex h-4 w-4 items-center justify-center rounded border text-[10px] ${
      checked
        ? 'border-blue-500 bg-blue-500 text-white'
        : partial
          ? 'border-blue-400 bg-blue-100 text-blue-500'
          : 'border-gray-300'
    }`}>
      {checked ? '✓' : partial ? '−' : ''}
    </span>
  )
}
