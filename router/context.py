"""
RouteContext：路由判断所需的全部信号。

所有字段均在 base model 完成 extract + grade 之后才可组装，
不存在时序问题。
"""
from __future__ import annotations

from dataclasses import dataclass

from models.schemas import QuestionType


@dataclass
class RouteContext:
    # 来自 QuestionData（extractor 产出）
    image_quality:          str           # "good" | "fair" | "poor"
    extraction_confidence:  float         # 0.0–1.0
    working_steps_count:    int           # len(working_steps)
    student_answer:         str

    # 来自 GradeResult（grader 调用 classifier 后产出）
    question_type:          QuestionType
    grading_confidence:     float         # 0.0–1.0，LLM 自评把握度
    needs_review:           bool          # grader 主动标记
