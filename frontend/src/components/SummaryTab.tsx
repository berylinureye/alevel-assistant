import { useEffect, useMemo, useState } from 'react'
import {
  aggregateKnowledgePoints,
  computeAccuracySeries,
  loadHistory,
  type AccuracyPoint,
  type KnowledgeAggregate,
  type SubtopicChapterMap,
} from '../lib/history'
import { fetchTaxonomy } from '../api/practice'

function ChapterChips({ data }: { data: KnowledgeAggregate[] }) {
  // 只展示已映射到 Paper / 章节的条目
  const chapters = data.filter((d) => d.tag.startsWith('Paper '))
  if (chapters.length === 0) {
    return <p className="text-sm text-gray-500">暂无错题章节数据。</p>
  }
  // 错题率排序：全对的放后面
  const sorted = [...chapters].sort((a, b) => {
    const ra = a.totalCount ? a.wrongCount / a.totalCount : 0
    const rb = b.totalCount ? b.wrongCount / b.totalCount : 0
    return rb - ra
  })
  const colorFor = (rate: number): string => {
    if (rate === 0) return 'border-green-500 text-green-700 bg-green-50'
    if (rate <= 0.3) return 'border-amber-500 text-amber-700 bg-amber-50'
    return 'border-red-500 text-red-700 bg-red-50'
  }
  return (
    <div className="flex flex-wrap gap-2">
      {sorted.map((d) => {
        const rate = d.totalCount > 0 ? d.wrongCount / d.totalCount : 0
        const label = d.tag.replace(/^Paper /, 'P')
        return (
          <span
            key={d.tag}
            title={`${d.tag} — 错 ${d.wrongCount} / 共 ${d.totalCount}`}
            className={`inline-flex items-center rounded-full border-2 border-dashed px-4 py-1.5 text-xs font-medium ${colorFor(rate)}`}
          >
            {label}
          </span>
        )
      })}
    </div>
  )
}

function AccuracyLineChart({ data }: { data: AccuracyPoint[] }) {
  const width = 640
  const height = 240
  const padding = { top: 20, right: 20, bottom: 40, left: 40 }
  const plotW = width - padding.left - padding.right
  const plotH = height - padding.top - padding.bottom

  if (data.length === 0) {
    return <p className="text-sm text-gray-500">暂无正确率数据。</p>
  }

  const xStep = data.length > 1 ? plotW / (data.length - 1) : 0
  const points = data.map((d, i) => {
    const x = padding.left + (data.length === 1 ? plotW / 2 : i * xStep)
    const y = padding.top + (1 - d.accuracy) * plotH
    return { x, y, d }
  })

  const pathD = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
    .join(' ')

  const yTicks = [0, 0.25, 0.5, 0.75, 1]

  const fmt = (ts: number) => {
    const d = new Date(ts)
    return `${d.getMonth() + 1}/${d.getDate()}`
  }

  return (
    <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full min-w-[480px]" role="img">
        {yTicks.map((t) => {
          const y = padding.top + (1 - t) * plotH
          return (
            <g key={t}>
              <line
                x1={padding.left}
                x2={width - padding.right}
                y1={y}
                y2={y}
                stroke="#e5e7eb"
                strokeDasharray="2 3"
              />
              <text
                x={padding.left - 6}
                y={y + 3}
                textAnchor="end"
                fontSize="10"
                fill="#6b7280"
              >
                {Math.round(t * 100)}%
              </text>
            </g>
          )
        })}

        <path d={pathD} fill="none" stroke="#2563eb" strokeWidth={2} />

        {points.map((p, i) => (
          <g key={i}>
            <circle cx={p.x} cy={p.y} r={3.5} fill="#2563eb" />
            {i === 0 || i === points.length - 1 || i % Math.ceil(points.length / 6) === 0 ? (
              <text
                x={p.x}
                y={height - padding.bottom + 14}
                textAnchor="middle"
                fontSize="10"
                fill="#6b7280"
              >
                {fmt(p.d.timestamp)}
              </text>
            ) : null}
          </g>
        ))}
      </svg>
    </div>
  )
}

export function SummaryTab() {
  const [records] = useState(() => loadHistory())
  const [chapterMap, setChapterMap] = useState<SubtopicChapterMap | undefined>(undefined)

  useEffect(() => {
    let cancelled = false
    fetchTaxonomy()
      .then((resp) => {
        if (cancelled) return
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
        setChapterMap(map)
      })
      .catch(() => {
        // 分类表拉不到就退回显示原始 tag
      })
    return () => {
      cancelled = true
    }
  }, [])

  const weak = useMemo(
    () => aggregateKnowledgePoints(records, chapterMap),
    [records, chapterMap],
  )
  const accuracy = useMemo(() => computeAccuracySeries(records), [records])

  const totals = useMemo(() => {
    let correct = 0
    let wrong = 0
    let unanswered = 0
    for (const r of records) {
      for (const q of r.questions) {
        if (q.unanswered) unanswered++
        else if (q.is_correct) correct++
        else wrong++
      }
    }
    const answered = correct + wrong
    return {
      correct,
      wrong,
      unanswered,
      total: correct + wrong + unanswered,
      accuracy: answered > 0 ? Math.round((correct / answered) * 100) : 0,
    }
  }, [records])

  if (records.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-gray-300 bg-white p-8 text-center text-sm text-gray-500">
        还没有批改记录，先去"作业批改"完成一次吧。
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-gray-900">总结</h2>

      <section className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <div className="rounded-lg border border-gray-200 bg-white p-3">
          <p className="text-xs text-gray-500">总题数</p>
          <p className="mt-1 text-xl font-semibold text-gray-900">{totals.total}</p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-3">
          <p className="text-xs text-gray-500">总正确率</p>
          <p className="mt-1 text-xl font-semibold text-green-600">{totals.accuracy}%</p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-3">
          <p className="text-xs text-gray-500">错题</p>
          <p className="mt-1 text-xl font-semibold text-red-600">{totals.wrong}</p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-3">
          <p className="text-xs text-gray-500">未作答</p>
          <p className="mt-1 text-xl font-semibold text-gray-600">{totals.unanswered}</p>
        </div>
      </section>

      <section className="rounded-lg border border-gray-200 bg-white p-4">
        <h3 className="text-sm font-semibold text-gray-900">章节掌握情况</h3>
        <p className="mt-1 text-xs text-gray-500">
          按 Paper / 章节汇总 · <span className="text-green-700">绿色</span> 全对，
          <span className="text-amber-700">黄色</span> 偶有出错，
          <span className="text-red-700">红色</span> 错题较多
        </p>
        <div className="mt-4">
          <ChapterChips data={weak} />
        </div>
      </section>

      <section className="rounded-lg border border-gray-200 bg-white p-4">
        <h3 className="text-sm font-semibold text-gray-900">正确率趋势</h3>
        <p className="mt-1 text-xs text-gray-500">按天汇总当日所有批改的正确率</p>
        <div className="mt-4">
          <AccuracyLineChart data={accuracy} />
        </div>
      </section>
    </div>
  )
}
