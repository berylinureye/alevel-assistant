"""题库 Pydantic 数据模型"""
from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class MathTopic(str, Enum):
    """数学知识点大类 — 与现有 QuestionType 对齐"""
    differentiation = "differentiation"
    integration = "integration"
    stationary_points = "stationary_points"
    algebra = "algebra"
    trigonometry = "trigonometry"
    vectors = "vectors"
    sequences_series = "sequences_series"
    coordinate_geometry = "coordinate_geometry"
    logarithms_exponentials = "logarithms_exponentials"
    statistics = "statistics"
    probability = "probability"
    mechanics = "mechanics"
    complex_numbers = "complex_numbers"
    differential_equations = "differential_equations"
    numerical_methods = "numerical_methods"
    unknown = "unknown"


class QuestionBankItem(BaseModel):
    """题库中的一道题"""
    id: Optional[int] = None
    paper_id: Optional[int] = None

    # 题目信息
    question_number: str = Field(description="题号, e.g. '1', '2(a)', '3(b)(ii)'")
    parent_number: Optional[str] = Field(default=None, description="父题号")
    parent_stem: Optional[str] = Field(default=None, description="父题题干或前序小问上下文")
    question_text: str = Field(description="题目文字 (含 LaTeX)")
    marks: int = Field(default=0, description="分值")

    # 分类
    topic: str = Field(default="unknown", description="知识点大类")
    subtopic: Optional[str] = Field(default=None, description="知识点子类")
    difficulty: int = Field(default=3, ge=1, le=5, description="难度 1-5")

    # 图表
    has_diagram: bool = Field(default=False)
    diagram_description: Optional[str] = None

    # 答案和评分
    correct_answer: Optional[str] = Field(default=None, description="正确答案 (LaTeX)")
    marking_points: Optional[list[str]] = Field(default=None, description="评分点列表")
    common_errors: Optional[list[str]] = Field(default=None, description="常见错误")

    # 来源
    subject_code: Optional[str] = "9709"
    year: Optional[int] = None
    session: Optional[str] = None
    paper_num: Optional[int] = None
    variant: Optional[int] = None
    source_page: Optional[int] = None

    # 状态
    parse_confidence: float = Field(default=0.0, description="AI 解析置信度")
    verified: bool = Field(default=False, description="是否已人工审核")
    tags: list[str] = Field(default_factory=list, description="知识点标签")


class RandomQuestionRequest(BaseModel):
    """随机出题请求参数"""
    topics: Optional[list[str]] = Field(default=None, description="知识点筛选")
    difficulty_min: int = Field(default=1, ge=1, le=5)
    difficulty_max: int = Field(default=5, ge=1, le=5)
    count: int = Field(default=5, ge=1, le=200)
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    paper_nums: Optional[list[int]] = None
    exclude_ids: Optional[list[int]] = Field(default=None, description="排除已做过的题目 ID")
    verified_only: bool = Field(default=False)


class RandomQuestionResponse(BaseModel):
    """随机出题响应"""
    status: str = "success"
    questions: list[QuestionBankItem]
    total_available: int


class SubmitAnswerRequest(BaseModel):
    """提交答案请求"""
    question_id: int
    student_answer: str
    working_steps: list[str] = Field(default_factory=list)


class TopicStats(BaseModel):
    """知识点统计"""
    topic: str
    count: int
    avg_difficulty: float
    year_range: str


class QuestionBankStats(BaseModel):
    """题库总体统计"""
    total_questions: int
    total_papers: int
    year_range: str
    topics: list[TopicStats]
    verified_count: int
    unverified_count: int
