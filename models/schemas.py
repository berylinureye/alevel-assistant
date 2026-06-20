from __future__ import annotations
from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, Field, PrivateAttr


class QuestionSegment(BaseModel):
    """Segmenter 的输出：整页图切出的单题区域"""

    question_number: str
    bbox: List[int] = Field(description="[x1, y1, x2, y2]，像素坐标")
    cropped_image: Any = Field(description="PIL.Image 裁剪图，不序列化")

    model_config = {"arbitrary_types_allowed": True}


class QuestionData(BaseModel):
    """Extractor 的输出：单题结构化信息，最终 JSON 字段"""

    question_number: str
    bbox: List[int] = Field(description="[x1, y1, x2, y2]，来自 segmenter")
    question_text: str = Field(description="题目文字（包含条件、公式等）")
    student_answer: str = Field(description="学生最终写下的答案")
    working_steps: List[str] = Field(description="学生的演算步骤列表")
    marks: int = Field(default=0, description="题目分值，从 [2][3] 等标注提取，0 表示未知")
    # 跨页/孤儿子题场景：这是本小题所属父题的题干（如 (ii) 依赖的完整 setup）。
    # segmenter 检测到裸 "(i)"/"(a)" 等孤儿 qnum 且上游有可用父题时回填；其他情况保持 None。
    parent_stem: Optional[str] = Field(default=None, description="父题题干，仅孤儿子题才有")
    # 图表题识别：学生以作图作答（stem-and-leaf / histogram / box-plot 等）时置 True。
    # 走这条分支的题目会跳过自动判分，改为生成作图指引 + 标记 needs_review。
    contains_diagram: bool = Field(default=False, description="学生是否以作图作答")
    diagram_type: Optional[str] = Field(
        default=None,
        description="图表类型：stem_leaf | histogram | box_plot | cumulative_frequency | scatter | bar_chart | other",
    )
    # --- 以下两个字段当前由 Claude 主观估计，后续可接专用评估模型 ---
    image_quality: str = Field(description="图像清晰度：good / fair / poor")
    confidence: float = Field(description="提取置信度 0.0~1.0")
    mark_scheme_context: Optional[str] = Field(
        default=None,
        description="官方 mark scheme 中与本题对应的简短评分上下文，仅后端用于批改 prompt",
    )


# ---------------------------------------------------------------------------
# Grader schemas
# ---------------------------------------------------------------------------

class QuestionType(str, Enum):
    differentiation        = "differentiation"
    integration            = "integration"
    stationary_points      = "stationary_points"
    algebra                = "algebra"
    trigonometry           = "trigonometry"
    vectors                = "vectors"
    sequences_series       = "sequences_series"
    coordinate_geometry    = "coordinate_geometry"
    logarithms_exponentials = "logarithms_exponentials"
    statistics             = "statistics"
    unknown                = "unknown"


class GradeResult(BaseModel):
    """Grader 的输出：单题批改结果"""

    question_number:    str
    question_type:      QuestionType
    is_correct:         bool
    score:              float = Field(description="实际得分")
    full_score:         float = Field(description="满分，MVP 默认 5")
    error_type:         Optional[str] = Field(
        description=(
            "correct | sign_error | missing_constant | wrong_rule | "
            "arithmetic_error | incomplete_working | unknown"
        )
    )
    knowledge_tags:     List[str] = Field(description="涉及的知识点标签")
    needs_review:       bool  = Field(description="置信度低或歧义时置 True，供老师人工复查")
    short_feedback:     str   = Field(description="1-2 句反馈，不展开讲解")
    # --- 路由层使用的字段 ---
    grading_confidence: float = Field(default=0.5, description="LLM 自评批改把握度 0.0~1.0")
    syllabus_topics:    List[dict] = Field(
        default_factory=list,
        description="A-Level 大纲定位: [{chapter, topic, subtopic, spec_ref}]",
    )
    relevant_formulas:  List[str] = Field(
        default_factory=list,
        description="本题应掌握的关键公式",
    )
    correct_answer:     Optional[str] = Field(default=None, description="正确答案（LaTeX 格式）")
    unanswered:         bool = Field(default=False, description="学生是否未作答此题")
    student_feedback:   Optional[str] = Field(default=None, description="面向学生的反馈（由 grading 一并生成）")
    teacher_feedback:   Optional[str] = Field(default=None, description="面向老师的反馈（由 grading 一并生成）")
    escalation_reasons: List[str] = Field(default_factory=list, description="触发升级的规则名列表")
    # 细节失分项：答案值正确但表述问题扣的分（未化简、未写单位、近似过早等）。
    # 每项 {tag: 短标签, detail: 具体说明, lost_points: 扣的分数}，前端渲染为彩色 pill。
    detail_deductions:  List[dict] = Field(
        default_factory=list,
        description="细节失分项：[{tag, detail, lost_points}]",
    )

    # 私有：multi-agent 批改后附带的各 agent 推理素材，供「解题思路 aggregator」复用。
    # PrivateAttr 不参与 model_dump() 序列化，不会泄漏到前端 JSON。
    _agent_deliberations: List[dict] = PrivateAttr(default_factory=list)


# ---------------------------------------------------------------------------
# Formatter schemas
# ---------------------------------------------------------------------------

class QuestionFeedback(BaseModel):
    """Feedback 层输出：单题双视角反馈"""

    question_number:  str
    student_feedback: str = Field(description="面向学生，≤50词，直接指出错误 + 一步建议")
    teacher_feedback: str = Field(description="面向老师，≤80词，失分点 + 知识漏洞 + 教学建议")


class PageSummary(BaseModel):
    """整页汇总：统计字段由 Python 规则计算，comment 由 LLM 生成"""

    total_questions:         int
    correct_count:           int
    incorrect_count:         int   # sum(1 for g if not g.is_correct and not g.unanswered)
    unanswered_count:        int = 0  # sum(1 for g if g.unanswered)
    review_count:            int   # sum(1 for g if g.needs_review)
    score_total:             float
    full_score_total:        float
    common_error_types:      List[str]        # 出现≥2次，排除 correct/unknown/""
    knowledge_tags_summary:  dict             # tag(归一化) → 出现次数
    estimated_review_minutes: int = 0
    priority_topics:          List[dict] = Field(default_factory=list)
    overall_teacher_comment: str              # LLM 生成，失败时降级为保守文案
