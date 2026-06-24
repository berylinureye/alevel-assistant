"""
API 专用 Pydantic 模型。

这里的 schema 只服务于 HTTP 层（请求/响应），
不替代 models/schemas.py 中的业务模型。
"""
from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 请求参数
# ---------------------------------------------------------------------------

class FeedbackMode(str, Enum):
    student = "student"
    teacher = "teacher"
    both    = "both"


class ReviewMode(str, Enum):
    auto  = "auto"
    force = "force"
    off   = "off"


# ---------------------------------------------------------------------------
# 响应 — 子模型
# ---------------------------------------------------------------------------

class RoutingInfoResponse(BaseModel):
    used_model:         str
    escalated:          bool
    escalation_reasons: list[str]


class QuestionResponse(BaseModel):
    # 来自 QuestionData
    question_number: str
    bbox:            list[int]
    question_text:   str
    parent_stem:     Optional[str] = None
    student_answer:  str
    working_steps:   list[str]
    image_quality:   str
    confidence:      float
    # 来自 GradeResult
    is_correct:      bool
    grading_confidence: float
    score:           float
    full_score:      float
    error_type:      Optional[str]
    knowledge_tags:  list[str]
    needs_review:    bool
    short_feedback:  str
    escalation_reasons: list[str]
    syllabus_topics:    list[dict] = []
    relevant_formulas: list[str] = []
    correct_answer:  Optional[str] = None
    unanswered:      bool = False
    # 细节失分项：[{tag, detail, lost_points}]。前端渲染为彩色 pill，提醒学生注意
    # 答案值虽然对但表述扣的小分（如未化简、未约分、近似过早等）
    detail_deductions: list[dict] = Field(default_factory=list)
    # 来自 QuestionFeedback（按 feedback_mode 过滤，可为 None）
    student_feedback: Optional[str]
    teacher_feedback: Optional[str]
    # 解题思路（批改后自动生成，缓存在响应中）
    solution_text:   Optional[str] = None
    # Past Paper / mark scheme route metadata. These fields tell the UI
    # whether the question was actually graded with official context or
    # conservatively fell back to open AI grading.
    grading_route: Optional[str] = None
    mark_scheme_confidence: Optional[str] = None
    mark_scheme_context_error: Optional[str] = None
    questionbank_question_id: Optional[int] = None
    questionbank_match_confidence: Optional[str] = None
    # 路由元信息
    routing_info:    RoutingInfoResponse


class PageSummaryResponse(BaseModel):
    total_questions:         int
    correct_count:           int
    incorrect_count:         int
    unanswered_count:        int = 0
    review_count:            int
    score_total:             float
    full_score_total:        float
    common_error_types:      list[str]
    knowledge_tags_summary:  dict[str, int]
    overall_teacher_comment: str
    estimated_review_minutes: int = 0
    priority_topics:          list[dict] = []


class DebugSegmentResponse(BaseModel):
    question_number: str
    bbox:            list[int]


class DebugArtifactsResponse(BaseModel):
    image_size:           list[int]             # [width, height]
    segments:             list[DebugSegmentResponse]
    annotated_image_b64:  Optional[str]         # None 表示 annotation 失败，降级


class GradeResultResponse(BaseModel):
    question_number:    str
    question_type:      str
    is_correct:         bool
    score:              float
    full_score:         float
    error_type:         Optional[str]
    knowledge_tags:     list[str]
    needs_review:       bool
    short_feedback:     str
    grading_confidence: float


class GradeQuestionRequest(BaseModel):
    question_number: str
    question_text:   str
    student_answer:  str
    working_steps:   list[str] = []
    image_quality:   str       = "good"
    confidence:      float     = 1.0


class GradeQuestionResponse(BaseModel):
    status:       str = "success"
    grade_result: GradeResultResponse
    used_model:   str


class ReviewQuestionRequest(BaseModel):
    question_number: str
    question_text:   str
    student_answer:  str
    working_steps:   list[str] = []
    image_quality:   str       = "good"
    confidence:      float     = 1.0
    include_base:    bool      = True


class ReviewQuestionResponse(BaseModel):
    status:        str = "success"
    base_result:   Optional[GradeResultResponse] = None
    review_result: GradeResultResponse
    final_result:  GradeResultResponse
    review_notes:  list[str]


class OverrideQuestionRequest(BaseModel):
    question_number:  str
    is_correct:       Optional[bool]  = None
    score:            Optional[float] = None
    full_score:       Optional[float] = None
    error_type:       Optional[str]   = None
    student_feedback: Optional[str]   = None
    teacher_feedback: Optional[str]   = None
    teacher_note:     Optional[str]   = None


class OverrideQuestionResponse(BaseModel):
    status:            str = "success"
    question_number:   str
    overridden_fields: list[str]
    result:            dict


class ExplainQuestionRequest(BaseModel):
    question_text:   str
    student_answer:  str
    working_steps:   list[str] = Field(default_factory=list)
    is_correct:      bool
    error_type:      Optional[str] = None
    score:           float = 0.0
    full_score:      float = 5.0
    correct_answer:  Optional[str] = None


class ExplainQuestionResponse(BaseModel):
    status:               str = "success"
    solution_explanation: str


class ChatQuestionRequest(BaseModel):
    question_text:    str
    student_answer:   str
    error_type:       Optional[str] = None
    solution_context: str = ""
    conversation:     list[dict] = Field(default_factory=list)
    new_message:      str
    # 讲解递进层级：1 = 拆细步骤（默认）；2 = 换数字/换角度；3 = 回退前置知识
    # 点一次"换个方式解释"就 +1，点"听懂了"重置为 1
    explain_level:    int = 1


class ChatQuestionResponse(BaseModel):
    status: str = "success"
    reply:  str


# ---------------------------------------------------------------------------
# 响应 — 顶层
# ---------------------------------------------------------------------------

class HomeworkResponse(BaseModel):
    status:          str = "success"
    questions:       list[QuestionResponse]
    page_summary:    PageSummaryResponse
    debug_artifacts: Optional[DebugArtifactsResponse] = None


class ApiErrorResponse(BaseModel):
    status:     str = "error"
    error_code: str
    message:    str
