import type {
  PracticeRecommendationResponse,
  QuestionBankItem,
} from '../types/practice'
import type { PageSummary, QuestionResult } from '../types'

const baseQuestion: QuestionBankItem = {
  id: 101,
  paper_id: 11,
  question_number: '5',
  parent_number: null,
  question_text: 'Solve \\(2x^2 - 5x - 3 = 0\\).',
  marks: 4,
  topic: 'quadratics',
  subtopic: 'quadratic_equations',
  difficulty: 2,
  has_diagram: false,
  diagram_description: null,
  correct_answer: '\\(x = 3\\) or \\(x = -\\frac{1}{2}\\)',
  marking_points: ['factorise the quadratic', 'solve both linear factors'],
  common_errors: ['only gives one root'],
  subject_code: '9709',
  year: 2024,
  session: 's',
  paper_num: 1,
  variant: 2,
  source_page: 8,
  parse_confidence: 0.94,
  verified: true,
  tags: ['quadratics'],
}

export const practiceReplaySummary: PageSummary = {
  total_questions: 3,
  correct_count: 1,
  incorrect_count: 2,
  unanswered_count: 0,
  review_count: 0,
  score_total: 6,
  full_score_total: 12,
  common_error_types: ['algebra_slip'],
  knowledge_tags_summary: { quadratics: 2 },
  estimated_review_minutes: 18,
  priority_topics: [
    {
      topic: 'quadratics',
      subtopic: 'quadratic_equations',
      chapter: 'Pure Mathematics 1',
      error_count: 2,
      key_formulas: [],
    },
  ],
  overall_teacher_comment: '先把二次方程因式分解和根的检查补稳。',
}

export const practiceReplayQuestions: QuestionResult[] = [
  {
    question_number: '5',
    bbox: [],
    question_text: baseQuestion.question_text,
    student_answer: 'x = 3',
    working_steps: ['2x^2 - 5x - 3 = 0', '(2x + 1)(x - 3) = 0'],
    image_quality: 'good',
    confidence: 0.95,
    is_correct: false,
    grading_confidence: 0.88,
    score: 2,
    full_score: 4,
    error_type: 'missing_solution',
    knowledge_tags: ['quadratics'],
    needs_review: false,
    short_feedback: '方法对，但漏写了另一个根。',
    escalation_reasons: [],
    student_feedback: '你已经完成了因式分解，最后要检查两个因子都对应一个解。',
    teacher_feedback: null,
    routing_info: { used_model: 'student-facing', escalated: false, escalation_reasons: [] },
    syllabus_topics: [],
    relevant_formulas: [],
    correct_answer: baseQuestion.correct_answer,
    unanswered: false,
    solution_text: null,
    grading_route: 'past_paper_mark_scheme',
    mark_scheme_confidence: 'high',
    mark_scheme_context_error: null,
  },
]

export const autoRecommendationFixture: PracticeRecommendationResponse = {
  status: 'success',
  recommendation_mode: 'auto',
  message: '已根据本次 Past Paper 批改结果推荐同主题练习。',
  detected_topic: 'quadratics',
  detected_subtopic: 'quadratic_equations',
  paper_num: 1,
  match_confidence: 'high',
  recommendations: [
    {
      id: 'foundation-101',
      question_id: 101,
      topic: 'quadratics',
      subtopic: 'quadratic_equations',
      difficulty: 'foundation',
      title: '基础修复',
      reason: '本次漏写一个根，先用低难度题稳住完整解集。',
      source_label: '同 Paper 1 · 同 topic',
      trigger: 'auto',
      paper_num: 1,
      requires_confirmation: false,
      question: baseQuestion,
    },
  ],
}

export const askFirstRecommendationFixture: PracticeRecommendationResponse = {
  status: 'success',
  recommendation_mode: 'ask_first',
  message: '我检测到这题像是 P1 Quadratics。要不要再做 2-3 道类似题来确认这个点？',
  detected_topic: 'quadratics',
  detected_subtopic: 'quadratic_equations',
  paper_num: 1,
  match_confidence: 'medium',
  recommendations: [],
}

export const unavailableRecommendationFixture: PracticeRecommendationResponse = {
  status: 'success',
  recommendation_mode: 'none',
  message:
    '这次我还不能可靠地为你匹配练习题。当前题目可能不属于 CIE 9709 P1-P6，建议先让老师确认题目来源。',
  detected_topic: null,
  detected_subtopic: null,
  paper_num: null,
  match_confidence: 'low',
  recommendations: [],
}
