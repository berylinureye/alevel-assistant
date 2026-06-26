import type { LargePdfPrepareResponse } from '../types'

function thumbnail(page: number): string {
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="360" height="510" viewBox="0 0 360 510">
      <rect width="360" height="510" fill="#f8fafc"/>
      <rect x="28" y="30" width="304" height="450" rx="8" fill="#ffffff" stroke="#cbd5e1"/>
      <text x="48" y="70" font-family="Arial" font-size="18" font-weight="700" fill="#0f172a">9709 Paper 12</text>
      <text x="48" y="98" font-family="Arial" font-size="13" fill="#64748b">Page ${page}</text>
      <line x1="48" y1="132" x2="300" y2="132" stroke="#cbd5e1" stroke-width="2"/>
      <text x="48" y="172" font-family="Arial" font-size="16" font-weight="700" fill="#1d4ed8">Q${Math.max(1, page - 1)}</text>
      <text x="82" y="172" font-family="Arial" font-size="13" fill="#334155">A-Level Mathematics working shown here...</text>
      <line x1="48" y1="214" x2="292" y2="214" stroke="#e2e8f0"/>
      <line x1="48" y1="246" x2="270" y2="246" stroke="#e2e8f0"/>
      <line x1="48" y1="278" x2="308" y2="278" stroke="#e2e8f0"/>
      <line x1="48" y1="310" x2="244" y2="310" stroke="#e2e8f0"/>
      <rect x="48" y="354" width="132" height="46" rx="6" fill="#eff6ff" stroke="#bfdbfe"/>
      <text x="62" y="382" font-family="Arial" font-size="12" fill="#1d4ed8">student answer</text>
    </svg>
  `
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
}

export const largePdfReplayFixture: LargePdfPrepareResponse = {
  status: 'ready',
  pdf_id: 'fixture-large-pdf',
  filename: '9709_s22_qp_11.pdf',
  page_count: 20,
  paper_resolution: {
    upload_intent: 'full_past_paper_pdf',
    paper_code: '9709/11/M/J/22',
    question_numbers: ['3', '4', '7'],
    paper_id: '9709_s22_11',
    paper_label: 'CIE 9709/11 May/Jun 2022',
    match_confidence: 'medium',
    match_source: 'cover',
    grading_route: 'past_paper_mark_scheme',
    needs_user_confirmation: true,
  },
  preview_pages: Array.from({ length: 20 }, (_, idx) => {
    const page = idx + 1
    return {
      page,
      thumbnail_b64: thumbnail(page),
      width: 360,
      height: 510,
      selected_by_default: page > 1 && page < 20,
      ocr_hint:
        page === 1
          ? 'Cambridge International AS & A Level Mathematics 9709 Paper 11 May June 2022'
          : page === 20
            ? 'Additional Page If you use the following lined page to complete an answer'
          : `Question ${Math.max(1, page - 1)} working and answer area`,
    }
  }),
}
