/** 题库练习模式相关类型 */

export interface QuestionBankItem {
  id: number
  paper_id: number | null
  question_number: string
  parent_number: string | null
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
