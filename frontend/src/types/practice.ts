/** 题库练习模式相关类型 */

export interface QuestionBankItem {
  id: number
  paper_id: number | null
  question_number: string
  parent_number: string | null
  parent_stem?: string | null
  question_text: string
  marks: number
  topic: string
  subtopic: string | null
  difficulty: number
  has_diagram: boolean
  diagram_description: string | null
  correct_answer: string | null
  marking_points: string[] | null
  common_errors: string[] | null
  subject_code: string
  year: number | null
  session: string | null
  paper_num: number | null
  variant: number | null
  source_page: number | null
  parse_confidence: number
  verified: boolean
  tags: string[]
}

export interface RandomQuestionRequest {
  topics?: string[]
  difficulty_min?: number
  difficulty_max?: number
  count?: number
  year_from?: number
  year_to?: number
  paper_nums?: number[]
  exclude_ids?: number[]
  verified_only?: boolean
}

export interface RandomQuestionResponse {
  status: string
  questions: QuestionBankItem[]
  total_available: number
}

export interface SubmitAnswerRequest {
  question_id: number
  student_answer: string
  working_steps: string[]
}

export interface SubmitAnswerResponse {
  status: string
  question_id: number
  grade_result: {
    is_correct: boolean
    score: number
    full_score: number
    error_type: string | null
    short_feedback: string
    knowledge_tags: string[]
    student_feedback: string | null
  }
  reference_answer: string | null
  marking_points: string[] | null
  source: {
    year: number
    session: string
    paper: number
    variant: number
    question_number: string
  }
}

export interface TopicStats {
  topic: string
  count: number
  avg_difficulty: number
  year_range: string
}

export interface QuestionBankStats {
  total_questions: number
  total_papers: number
  year_range: string
  topics: TopicStats[]
  verified_count: number
  unverified_count: number
}

/** 练习会话中一道题的状态 */
export interface PracticeQuestionState {
  question: QuestionBankItem
  studentAnswer: string
  workingSteps: string[]
  submitted: boolean
  result: SubmitAnswerResponse | null
}

/** 练习配置 */
export interface PracticeConfig {
  topics: string[]
  difficultyMin: number
  difficultyMax: number
  count: number
}

export type PracticeRecommendationMode = 'auto' | 'ask_first' | 'none'
export type PracticeRecommendationTrigger = 'auto' | 'ask_first' | 'unavailable'
export type PracticeRecommendationDifficulty = 'foundation' | 'consolidation' | 'exam-style'
export type PracticeUploadIntent =
  | 'past_paper'
  | 'custom_homework'
  | 'unknown'
  | 'full_past_paper_pdf'
  | 'partial_past_paper_pages'
  | 'answer_pages_only'
  | 'single_question_photo'

export interface PracticeRecommendationContext {
  upload_intent: PracticeUploadIntent
  paper_num?: 1 | 2 | 3 | 4 | 5 | 6 | null
  question_number?: string | null
  match_confidence?: 'high' | 'medium' | 'low' | null
  confirmed_by_user: boolean
  grading_route?: 'past_paper_mark_scheme' | 'open_ai_grading' | null
  recommendation_mode?: PracticeRecommendationMode
}

export interface PracticeRecommendationSourceQuestion {
  question_number: string
  score: number
  full_score: number
  is_correct: boolean
  unanswered: boolean
  error_type: string | null
  knowledge_tags: string[]
  needs_review: boolean
  questionbank_question_id?: number | null
  questionbank_match_confidence?: 'high' | 'medium' | 'low' | null
}

export interface PracticeRecommendationPriorityTopic {
  topic: string
  subtopic?: string | null
  chapter?: string | null
  error_count?: number
}

export interface PracticeRecommendationRequest {
  context: PracticeRecommendationContext
  priority_topics: PracticeRecommendationPriorityTopic[]
  knowledge_tags_summary: Record<string, number>
  questions: PracticeRecommendationSourceQuestion[]
  exclude_ids: number[]
  preferred_difficulty_min?: number
  preferred_difficulty_max?: number
  count?: number
}

export interface PracticeRecommendation {
  id: string
  question_id: number | null
  topic: string
  subtopic?: string | null
  difficulty: PracticeRecommendationDifficulty
  title: string
  reason: string
  source_label?: string
  unavailable?: boolean
  trigger: PracticeRecommendationTrigger
  paper_num?: 1 | 2 | 3 | 4 | 5 | 6 | null
  requires_confirmation?: boolean
  question?: QuestionBankItem | null
}

export interface PracticeRecommendationResponse {
  status: string
  recommendation_mode: PracticeRecommendationMode
  message: string
  detected_topic?: string | null
  detected_subtopic?: string | null
  paper_num?: 1 | 2 | 3 | 4 | 5 | 6 | null
  match_confidence?: 'high' | 'medium' | 'low' | null
  recommendations: PracticeRecommendation[]
}

export interface PracticeLoopState {
  weak_topics: string[]
  recommended_ids: number[]
  completed_ids: number[]
  current_question_id?: number
  last_result?: {
    question_id: number
    is_correct: boolean
    score: number
    full_score: number
    error_type: string | null
  }
}
