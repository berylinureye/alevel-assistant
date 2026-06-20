import { useCallback, useEffect, useRef, useState } from 'react'
import { exportQuestions } from '../../api/practice'
import { renderLatex } from './latexUtils'
import type { PracticeConfig, QuestionBankItem } from '../../types/practice'
import jsPDF from 'jspdf'
import html2canvas from 'html2canvas'

const SESSION_LABELS: Record<string, string> = {
  s: 'Summer',
  w: 'Winter',
  m: 'Spring',
}

const TOPIC_LABELS: Record<string, string> = {
  differentiation: 'Differentiation',
  integration: 'Integration',
  stationary_points: 'Stationary Points',
  algebra: 'Algebra',
  trigonometry: 'Trigonometry',
  vectors: 'Vectors',
  sequences_series: 'Sequences & Series',
  coordinate_geometry: 'Coordinate Geometry',
  logarithms_exponentials: 'Logs & Exponentials',
  statistics: 'Statistics',
  probability: 'Probability',
  mechanics: 'Mechanics',
  complex_numbers: 'Complex Numbers',
  differential_equations: 'Differential Equations',
  numerical_methods: 'Numerical Methods',
}

interface Props {
  config: PracticeConfig
  onClose: () => void
}

export function ExportModal({ config, onClose }: Props) {
  const [questions, setQuestions] = useState<QuestionBankItem[]>([])
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [exportCount, setExportCount] = useState(config.count)
  const [includeAnswers, setIncludeAnswers] = useState(false)
  const printRef = useRef<HTMLDivElement>(null)

  const loadQuestions = useCallback(async (count: number) => {
    setLoading(true)
    setError(null)
    try {
      const resp = await exportQuestions({
        topics: config.topics.length > 0 ? config.topics : undefined,
        difficulty_min: config.difficultyMin,
        difficulty_max: config.difficultyMax,
        count,
      })
      setQuestions(resp.questions)
      if (resp.questions.length === 0) {
        setError('没有符合条件的题目')
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载题目失败')
    } finally {
      setLoading(false)
    }
  }, [config])

  useEffect(() => {
    loadQuestions(exportCount)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleExportPDF = async () => {
    if (!printRef.current || questions.length === 0) return

    setExporting(true)
    try {
      const element = printRef.current
      const canvas = await html2canvas(element, {
        scale: 2,
        useCORS: true,
        logging: false,
        backgroundColor: '#ffffff',
      })

      const imgData = canvas.toDataURL('image/png')
      const imgWidth = 210 // A4 width in mm
      const pageHeight = 297 // A4 height in mm
      const imgHeight = (canvas.height * imgWidth) / canvas.width

      const pdf = new jsPDF('p', 'mm', 'a4')
      let heightLeft = imgHeight
      let position = 0

      // First page
      pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight)
      heightLeft -= pageHeight

      // Additional pages
      while (heightLeft > 0) {
        position -= pageHeight
        pdf.addPage()
        pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight)
        heightLeft -= pageHeight
      }

      // Generate filename
      const topicStr = config.topics.length > 0
        ? config.topics.slice(0, 3).join('_')
        : 'all'
      const dateStr = new Date().toISOString().slice(0, 10)
      pdf.save(`practice_${topicStr}_${dateStr}.pdf`)
    } catch (e) {
      setError(e instanceof Error ? e.message : '导出 PDF 失败')
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4">
      <div className="relative mt-8 mb-8 w-full max-w-4xl rounded-lg bg-white shadow-xl">
        {/* Header */}
        <div className="sticky top-0 z-10 flex items-center justify-between rounded-t-lg border-b bg-white px-6 py-4">
          <h2 className="text-lg font-bold text-gray-800">导出习题为 PDF</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Controls */}
        <div className="flex flex-wrap items-center gap-4 border-b bg-gray-50 px-6 py-3">
          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-600">导出数量:</label>
            <select
              value={exportCount}
              onChange={(e) => {
                const v = Number(e.target.value)
                setExportCount(v)
                loadQuestions(v)
              }}
              className="rounded border border-gray-300 px-2 py-1 text-sm"
            >
              {[5, 10, 15, 20, 30, 50].map((n) => (
                <option key={n} value={n}>{n} 题</option>
              ))}
            </select>
          </div>

          <label className="flex items-center gap-1.5 text-sm text-gray-600">
            <input
              type="checkbox"
              checked={includeAnswers}
              onChange={(e) => setIncludeAnswers(e.target.checked)}
              className="rounded border-gray-300"
            />
            附带参考答案
          </label>

          <div className="flex-1" />

          <button
            type="button"
            onClick={() => loadQuestions(exportCount)}
            disabled={loading}
            className="rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 disabled:opacity-50"
          >
            换一批
          </button>

          <button
            type="button"
            onClick={handleExportPDF}
            disabled={exporting || loading || questions.length === 0}
            className="rounded bg-blue-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {exporting ? '生成中...' : '下载 PDF'}
          </button>
        </div>

        {/* Preview content */}
        <div className="max-h-[60vh] overflow-y-auto px-6 py-4">
          {loading && (
            <div className="flex items-center justify-center py-12">
              <p className="text-sm text-gray-400">加载题目中...</p>
            </div>
          )}

          {error && (
            <p className="py-8 text-center text-sm text-red-600">{error}</p>
          )}

          {!loading && questions.length > 0 && (
            <div ref={printRef} className="space-y-0 bg-white" style={{ padding: '20px' }}>
              {/* PDF Title */}
              <div style={{ marginBottom: '24px', borderBottom: '2px solid #333', paddingBottom: '12px' }}>
                <h1 style={{ fontSize: '20px', fontWeight: 'bold', color: '#1a1a1a', margin: '0 0 4px 0' }}>
                  A-Level Mathematics Practice
                </h1>
                <p style={{ fontSize: '12px', color: '#666', margin: 0 }}>
                  {config.topics.length > 0
                    ? `Topics: ${config.topics.map(t => TOPIC_LABELS[t] || t).join(', ')}`
                    : 'All Topics'}
                  {' | '}Difficulty: {config.difficultyMin}-{config.difficultyMax}
                  {' | '}{questions.length} Questions
                  {' | '}Date: {new Date().toLocaleDateString()}
                </p>
              </div>

              {/* Questions */}
              {questions.map((q, i) => (
                <div key={q.id} style={{ marginBottom: '20px', pageBreakInside: 'avoid' }}>
                  {/* Question header */}
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', marginBottom: '6px' }}>
                    <span style={{ fontSize: '14px', fontWeight: 'bold', color: '#1a1a1a' }}>
                      {i + 1}.
                    </span>
                    <span style={{ fontSize: '11px', color: '#888' }}>
                      [{q.marks} marks]
                    </span>
                    <span style={{ fontSize: '10px', color: '#aaa' }}>
                      {q.topic} | Difficulty {'★'.repeat(q.difficulty)}{'☆'.repeat(5 - q.difficulty)}
                    </span>
                    {q.year && (
                      <span style={{ fontSize: '10px', color: '#bbb', marginLeft: 'auto' }}>
                        9709/{q.year} {SESSION_LABELS[q.session ?? ''] ?? ''} P{q.paper_num}
                      </span>
                    )}
                  </div>

                  {/* Question text */}
                  <div
                    style={{ fontSize: '13px', color: '#333', lineHeight: '1.7', paddingLeft: '16px' }}
                    dangerouslySetInnerHTML={{ __html: renderLatex(q.question_text) }}
                  />

                  {/* Answer space (lines) */}
                  {!includeAnswers && (
                    <div style={{ paddingLeft: '16px', marginTop: '12px' }}>
                      {Array.from({ length: Math.max(2, Math.ceil(q.marks / 2)) }).map((_, li) => (
                        <div key={li} style={{ borderBottom: '1px solid #e5e5e5', height: '28px' }} />
                      ))}
                    </div>
                  )}

                  {/* Reference answer (if enabled) */}
                  {includeAnswers && q.correct_answer && (
                    <div style={{ marginTop: '8px', paddingLeft: '16px', padding: '8px 16px', backgroundColor: '#f0fdf4', borderRadius: '4px', borderLeft: '3px solid #22c55e' }}>
                      <span style={{ fontSize: '11px', fontWeight: '600', color: '#15803d' }}>Answer: </span>
                      <span
                        style={{ fontSize: '12px', color: '#166534' }}
                        dangerouslySetInnerHTML={{ __html: renderLatex(q.correct_answer) }}
                      />
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
