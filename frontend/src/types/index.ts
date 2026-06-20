export interface RoutingInfo {
  used_model: string
  escalated: boolean
  escalation_reasons: string[]
}

/** 与大纲/考纲相关的知识点定位（若有） */
export interface SyllabusTopic {
  chapter: string
  topic: string
  subtopic: string
  spec_ref: string
}

export interface PriorityTopic {
  topic: string
  subtopic: string
  chapter: string
  error_count: number
  key_formulas: string[]
}

export interface QuestionResult {
  question_number: string
  bbox: number[]
  question_text: string
  /** 父题题干（多个小题共享的题设，例如随机变量定义、数据表、图形），无则为空/null */
  parent_stem?: string | null
  student_answer: string
  working_steps: string[]
  /** 所属页码（1-based），跨页题用来标记"图片 N" 前缀 */
  page?: number | null
  image_quality: string
  confidence: number
  is_correct: boolean
  grading_confidence: number
  score: number
  full_score: number
  error_type: string | null
  knowledge_tags: string[]
  needs_review: boolean
  short_feedback: string
  escalation_reasons: string[]
  student_feedback: string | null
  teacher_feedback: string | null
  routing_info: RoutingInfo
  syllabus_topics: SyllabusTopic[]
  /** 应掌握的公式（错题分析用） */
  relevant_formulas: string[]
  /** 正确答案 */
  correct_answer: string | null
  /** 学生是否未作答 */
  unanswered: boolean
  /** 预生成的解题思路（批改后自动缓存，可能为 null） */
  solution_text: string | null
  /** 细节失分项：答案值对但表述扣分（未化简、未约分等）。前端渲染为彩色 pill */
  detail_deductions?: Array<{ tag: string; detail: string; lost_points: number }>
  /** 本题实际批改路径：Past Paper mark scheme 或开放 AI 批改 */
  grading_route?: 'past_paper_mark_scheme' | 'open_ai_grading' | null
  /** 题目级 mark scheme 上下文抽取置信度 */
  mark_scheme_confidence?: 'high' | 'medium' | 'low' | null
  /** mark scheme 上下文不可用时的可见降级原因 */
  mark_scheme_context_error?: string | null
}

export interface PageSummary {
  total_questions: number
  correct_count: number
  incorrect_count: number
  unanswered_count: number
  review_count: number
  score_total: number
  full_score_total: number
  common_error_types: string[]
  knowledge_tags_summary: Record<string, number>
  estimated_review_minutes: number
  priority_topics: PriorityTopic[]
  overall_teacher_comment: string
}

export interface HomeworkResponse {
  status: string
  questions: QuestionResult[]
  page_summary: PageSummary
}

export type UploadIntent =
  | 'past_paper'
  | 'custom_homework'
  | 'unknown'
  | 'answer_pages_only'

export interface ApiError {
  status: string
  error_code: string
  message: string
}

export interface AnalyzeRequest {
  images: File[]
  /** 可选：告诉 AI 题目数量、大致位置等，便于切题 */
  user_hint?: string
  /** 可选：与 images 一一对应的 upload_id；已预提取完成时传入可跳过切题 */
  upload_ids?: (string | null | undefined)[]
  /** 上传意图：用于 Past Paper 路由和开放批改回退 */
  upload_intent?: UploadIntent
  /** 可选：CAIE paper code，例如 9709/12/M/J/16 */
  paper_code?: string
  /** 可选：优先批改的题号，例如 3, 4(a), 7 */
  question_numbers?: string
}

export interface ExplainQuestionRequest {
  question_text: string
  student_answer: string
  working_steps: string[]
  is_correct: boolean
  error_type: string | null
  score: number
  full_score: number
  correct_answer: string | null
}

export interface ExplainQuestionResponse {
  status: string
  solution_explanation: string
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

/** 讲解层级：1 拆细 / 2 换数字换角度 / 3 回退前置知识 */
export type ExplainLevel = 1 | 2 | 3

export interface ChatQuestionRequest {
  question_text: string
  student_answer: string
  error_type: string | null
  solution_context: string
  conversation: ChatMessage[]
  new_message: string
  explain_level?: ExplainLevel
}

export interface ChatQuestionResponse {
  status: string
  reply: string
}
