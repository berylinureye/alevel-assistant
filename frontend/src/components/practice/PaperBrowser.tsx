import { useCallback, useEffect, useState } from 'react'
import { fetchPapers, getPaperDownloadUrl } from '../../api/practice'
import type { PaperListItem } from '../../api/practice'

const SESSION_LABELS: Record<string, string> = {
  s: '夏季 May/Jun',
  w: '冬季 Oct/Nov',
  m: '春季 Feb/Mar',
}

const PAPER_NAMES: Record<number, string> = {
  1: 'P1 Pure Math 1',
  2: 'P2 Pure Math 2',
  3: 'P3 Pure Math 3',
  4: 'P4 Mechanics',
  5: 'P5 Statistics 1',
  6: 'P6 Statistics 2',
}

export function PaperBrowser({ defaultOpen = false }: { defaultOpen?: boolean } = {}) {
  const [papers, setPapers] = useState<PaperListItem[]>([])
  const [loading, setLoading] = useState(false)
  const [show, setShow] = useState(defaultOpen)

  // Filters
  const [filterPaper, setFilterPaper] = useState<number | undefined>()
  const [filterYear, setFilterYear] = useState<number | undefined>()
  const [filterSession, setFilterSession] = useState<string | undefined>()

  const loadPapers = useCallback(async () => {
    setLoading(true)
    try {
      const resp = await fetchPapers({
        paper_num: filterPaper,
        year: filterYear,
        session: filterSession,
      })
      setPapers(resp.papers)
    } catch {
      setPapers([])
    } finally {
      setLoading(false)
    }
  }, [filterPaper, filterSession, filterYear])

  useEffect(() => {
    if (show) loadPapers()
  }, [show, loadPapers])

  if (!show) {
    return (
      <button
        type="button"
        onClick={() => setShow(true)}
        className="w-full rounded-md border border-dashed border-gray-300 px-4 py-3 text-sm text-gray-500 hover:border-gray-400 hover:text-gray-700"
      >
        <span className="flex items-center justify-center gap-2">
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          浏览并下载历年真题 PDF
        </span>
      </button>
    )
  }

  // Group papers by year
  const grouped = papers.reduce<Record<number, PaperListItem[]>>((acc, p) => {
    ;(acc[p.year] ??= []).push(p)
    return acc
  }, {})
  const years = Object.keys(grouped)
    .map(Number)
    .sort((a, b) => b - a)

  return (
    <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-100 bg-gray-50 px-4 py-3">
        <h3 className="text-sm font-medium text-gray-700">历年真题下载</h3>
        <button
          type="button"
          onClick={() => setShow(false)}
          className="text-xs text-gray-400 hover:text-gray-600"
        >
          收起
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 border-b border-gray-100 px-4 py-3">
        <select
          value={filterPaper ?? ''}
          onChange={(e) => setFilterPaper(e.target.value ? Number(e.target.value) : undefined)}
          className="rounded border border-gray-300 px-2 py-1 text-xs"
        >
          <option value="">全部 Paper</option>
          {[1, 2, 3, 4, 5, 6].map((n) => (
            <option key={n} value={n}>{PAPER_NAMES[n]}</option>
          ))}
        </select>

        <select
          value={filterYear ?? ''}
          onChange={(e) => setFilterYear(e.target.value ? Number(e.target.value) : undefined)}
          className="rounded border border-gray-300 px-2 py-1 text-xs"
        >
          <option value="">全部年份</option>
          {Array.from({ length: 11 }, (_, i) => 2025 - i).map((y) => (
            <option key={y} value={y}>{y}</option>
          ))}
        </select>

        <select
          value={filterSession ?? ''}
          onChange={(e) => setFilterSession(e.target.value || undefined)}
          className="rounded border border-gray-300 px-2 py-1 text-xs"
        >
          <option value="">全部季节</option>
          <option value="s">夏季 May/Jun</option>
          <option value="w">冬季 Oct/Nov</option>
          <option value="m">春季 Feb/Mar</option>
        </select>

        {loading && <span className="text-xs text-gray-400">加载中...</span>}
        {!loading && <span className="text-xs text-gray-400">{papers.length} 份试卷</span>}
      </div>

      {/* Paper list */}
      <div className="max-h-80 overflow-y-auto">
        {years.map((year) => (
          <div key={year}>
            <div className="sticky top-0 bg-gray-50 px-4 py-1.5 text-xs font-medium text-gray-500 border-b border-gray-100">
              {year}
            </div>
            <div className="divide-y divide-gray-50">
              {grouped[year].map((p) => (
                <div key={p.id} className="flex items-center justify-between px-4 py-2 hover:bg-gray-50">
                  <div className="flex items-center gap-2 text-sm">
                    <span className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-medium ${
                      p.level === 'AS' ? 'bg-emerald-100 text-emerald-700' : 'bg-purple-100 text-purple-700'
                    }`}>
                      {p.level}
                    </span>
                    <span className="text-gray-700">
                      P{p.paper_num} {p.paper_name}
                    </span>
                    <span className="text-gray-400">V{p.variant}</span>
                    <span className="text-xs text-gray-400">
                      {SESSION_LABELS[p.session] ?? p.session}
                    </span>
                  </div>
                  <div className="flex gap-2">
                    {p.has_qp && (
                      <a
                        href={getPaperDownloadUrl(p.id, 'qp')}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="rounded border border-blue-200 bg-blue-50 px-2 py-0.5 text-[11px] text-blue-600 hover:bg-blue-100"
                      >
                        试题 QP
                      </a>
                    )}
                    {p.has_ms && (
                      <a
                        href={getPaperDownloadUrl(p.id, 'ms')}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="rounded border border-amber-200 bg-amber-50 px-2 py-0.5 text-[11px] text-amber-600 hover:bg-amber-100"
                      >
                        答案 MS
                      </a>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
        {!loading && papers.length === 0 && (
          <p className="px-4 py-6 text-center text-sm text-gray-400">没有找到试卷</p>
        )}
      </div>
    </div>
  )
}
