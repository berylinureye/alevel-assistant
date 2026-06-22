# Practice Orchestrator MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在批改结果页加入一个可测试的学习闭环：根据本次批改结果判断是否自动推荐题、是否先询问学生、或是否明确不推荐，并支持学生完成一道推荐题后得到下一步练习动作。

**Architecture:** 采用混合 agent 架构：规则负责上传意图、paper 范围、置信度和题库边界；模型批改结果负责暴露薄弱点；推荐编排器负责把这些输入转成 `auto / ask_first / none` 三种模式。后端新增薄编排接口负责题库查询和去重，前端负责结果页交互、询问式推荐和内联作答。

**Tech Stack:** FastAPI, Pydantic, SQLite question bank, React 19, TypeScript, Vite, Tailwind CSS, pytest, existing Chrome/CDP visual acceptance script.

---

## 执行分工

- 产品子智能体：确认学生可见文案、三种推荐模式、空状态和能力边界是否符合规格。
- 算法子智能体：实现 topic 推导、paper 范围判断、推荐模式决策、难度递进规则。
- 后端子智能体：实现 `/practice-orchestrator/recommendations`，接入 SQLite 题库并补 pytest。
- 前端子智能体：实现结果页 `下一步练习` UI、询问式推荐、内联作答和 replay 页面。
- 测试子智能体：运行后端测试、前端 build、focused lint、真实浏览器截图和 DOM 证据。
- 主智能体：按 Superpowers subagent-driven-development 协调任务；谁引入的 bug 由原子智能体修复，谁提出的问题由原测试子智能体验收。

## 文件结构

- Create: `api/practice_orchestrator.py`
  - 后端推荐编排器。定义请求/响应 schema、推荐模式决策、topic alias、题库查询和 FastAPI router。
- Modify: `api/app.py`
  - 注册 `practice_orchestrator_router`。
- Create: `test/test_practice_orchestrator.py`
  - 覆盖自动推荐、询问式推荐、不推荐、P1-P6 边界和 session 去重。
- Modify: `frontend/src/types/practice.ts`
  - 增加推荐编排相关类型。
- Create: `frontend/src/api/practiceOrchestrator.ts`
  - 调用后端推荐编排接口。
- Create: `frontend/src/components/practice/PracticeRecommendations.tsx`
  - 批改结果页的 `下一步练习` 区块，处理三种推荐模式和内联作答。
- Create: `frontend/src/fixtures/practiceOrchestratorReplay.ts`
  - 前端 replay fixture，覆盖 auto、ask_first、none 三种状态。
- Create: `frontend/src/pages/PracticeRecommendationsReplayPage.tsx`
  - 用真实组件渲染 replay，便于视觉验收。
- Modify: `frontend/src/main.tsx`
  - 开发环境增加 `/__practice-recommendations-replay` 路由。
- Modify: `frontend/src/App.tsx`
  - 保存最近一次上传上下文，把 `PracticeRecommendations` 插入 `PageSummary` 后面。
- Create: `frontend/scripts/replay-practice-orchestrator.mjs`
  - 静态 replay 检查，确保学生界面没有暴露 raw `think / act / observe`，且关键文案存在。
- Modify: `frontend/package.json`
  - 增加 `test:practice-orchestrator` 脚本。

---

### Task 1: 产品口径与前端类型

**Role:** 产品子智能体 + 前端子智能体

**Files:**
- Modify: `frontend/src/types/practice.ts`
- Create: `frontend/src/fixtures/practiceOrchestratorReplay.ts`

- [ ] **Step 1: 扩展前端类型**

在 `frontend/src/types/practice.ts` 末尾追加：

```ts
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
```

- [ ] **Step 2: 创建 replay fixture**

Create `frontend/src/fixtures/practiceOrchestratorReplay.ts`:

```ts
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
  message: '这次我还不能可靠地为你匹配练习题。当前题目可能不属于 CIE 9709 P1-P6，建议先让老师确认题目来源。',
  detected_topic: null,
  detected_subtopic: null,
  paper_num: null,
  match_confidence: 'low',
  recommendations: [],
}
```

- [ ] **Step 3: Run type check**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS. This task only adds types and a fixture, so the build should not require later wiring.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/practice.ts frontend/src/fixtures/practiceOrchestratorReplay.ts
git commit -m "Add practice recommendation frontend types"
```

---

### Task 2: 后端推荐编排接口

**Role:** 算法子智能体 + 后端子智能体

**Files:**
- Create: `api/practice_orchestrator.py`
- Modify: `api/app.py`
- Test: `test/test_practice_orchestrator.py`

- [ ] **Step 1: Write failing backend tests**

Create `test/test_practice_orchestrator.py`:

```python
from api.practice_orchestrator import (
    PracticeRecommendationContext,
    PracticeRecommendationRequest,
    choose_recommendation_mode,
    derive_candidate_topics,
    normalise_paper_num,
)


def test_confirmed_past_paper_uses_auto_mode():
    ctx = PracticeRecommendationContext(
        upload_intent="past_paper",
        paper_num=1,
        match_confidence="high",
        confirmed_by_user=False,
        grading_route="past_paper_mark_scheme",
    )

    assert choose_recommendation_mode(ctx, has_topic=True, has_review_risk=False) == "auto"


def test_single_question_photo_asks_first():
    ctx = PracticeRecommendationContext(
        upload_intent="single_question_photo",
        paper_num=5,
        match_confidence="medium",
        confirmed_by_user=False,
        grading_route="open_ai_grading",
    )

    assert choose_recommendation_mode(ctx, has_topic=True, has_review_risk=False) == "ask_first"


def test_confirmed_single_question_can_fetch_questions():
    ctx = PracticeRecommendationContext(
        upload_intent="single_question_photo",
        paper_num=5,
        match_confidence="medium",
        confirmed_by_user=True,
        grading_route="open_ai_grading",
    )

    assert choose_recommendation_mode(ctx, has_topic=True, has_review_risk=False) == "auto"


def test_low_confidence_without_topic_returns_none():
    ctx = PracticeRecommendationContext(
        upload_intent="unknown",
        paper_num=None,
        match_confidence="low",
        confirmed_by_user=False,
        grading_route="open_ai_grading",
    )

    assert choose_recommendation_mode(ctx, has_topic=False, has_review_risk=False) == "none"


def test_paper_num_is_limited_to_p1_to_p6():
    assert normalise_paper_num(1) == 1
    assert normalise_paper_num(6) == 6
    assert normalise_paper_num(7) is None
    assert normalise_paper_num(None) is None


def test_derives_topic_from_priority_topic_first():
    req = PracticeRecommendationRequest(
        context=PracticeRecommendationContext(
            upload_intent="past_paper",
            paper_num=1,
            match_confidence="high",
            confirmed_by_user=False,
            grading_route="past_paper_mark_scheme",
        ),
        priority_topics=[{"topic": "Quadratics", "subtopic": "quadratic equations"}],
        knowledge_tags_summary={"differentiation": 3},
        questions=[],
        exclude_ids=[],
    )

    topics = derive_candidate_topics(req)

    assert topics[0] == "quadratics"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest test/test_practice_orchestrator.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'api.practice_orchestrator'`.

- [ ] **Step 3: Create backend module**

Create `api/practice_orchestrator.py`:

```python
from __future__ import annotations

import re
from typing import Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from questionbank.database import ensure_db, get_random_questions
from questionbank.models import QuestionBankItem

PracticeRecommendationMode = Literal["auto", "ask_first", "none"]
PracticeUploadIntent = Literal[
    "past_paper",
    "custom_homework",
    "unknown",
    "full_past_paper_pdf",
    "partial_past_paper_pages",
    "answer_pages_only",
    "single_question_photo",
]

SUPPORTED_PAPERS = {1, 2, 3, 4, 5, 6}

TOPIC_ALIASES: dict[str, str] = {
    "quadratic": "quadratics",
    "quadratics": "quadratics",
    "quadratic equations": "quadratics",
    "function": "functions",
    "functions": "functions",
    "coordinate geometry": "coordinate_geometry",
    "circle": "coordinate_geometry",
    "circular measure": "circular_measure",
    "trigonometry": "trigonometry_p1",
    "trig": "trigonometry_p1",
    "series": "series",
    "sequence": "series",
    "differentiation": "differentiation_p1",
    "derivative": "differentiation_p1",
    "integration": "integration_p1",
    "integral": "integration_p1",
    "normal distribution": "normal_distribution",
    "probability": "probability",
    "kinematics": "kinematics",
    "forces": "forces_and_equilibrium",
    "complex numbers": "complex_numbers",
}

BROAD_TOPIC_BY_PAPER: dict[str, dict[int, str]] = {
    "trigonometry": {1: "trigonometry_p1", 2: "trigonometry_p2", 3: "trigonometry_p3"},
    "differentiation": {1: "differentiation_p1", 2: "differentiation_p2", 3: "differentiation_p3"},
    "integration": {1: "integration_p1", 2: "integration_p2", 3: "integration_p3"},
}


class PracticeRecommendationContext(BaseModel):
    upload_intent: PracticeUploadIntent = "unknown"
    paper_num: Optional[int] = None
    question_number: Optional[str] = None
    match_confidence: Optional[Literal["high", "medium", "low"]] = None
    confirmed_by_user: bool = False
    grading_route: Optional[Literal["past_paper_mark_scheme", "open_ai_grading"]] = None
    recommendation_mode: Optional[PracticeRecommendationMode] = None


class PracticeSourceQuestion(BaseModel):
    question_number: str
    score: float = 0
    full_score: float = 0
    is_correct: bool = False
    unanswered: bool = False
    error_type: Optional[str] = None
    knowledge_tags: list[str] = Field(default_factory=list)
    needs_review: bool = False


class PracticeRecommendationRequest(BaseModel):
    context: PracticeRecommendationContext
    priority_topics: list[dict] = Field(default_factory=list)
    knowledge_tags_summary: dict[str, int] = Field(default_factory=dict)
    questions: list[PracticeSourceQuestion] = Field(default_factory=list)
    exclude_ids: list[int] = Field(default_factory=list)
    preferred_difficulty_min: Optional[int] = Field(default=None, ge=1, le=5)
    preferred_difficulty_max: Optional[int] = Field(default=None, ge=1, le=5)
    count: int = Field(default=3, ge=1, le=6)


class PracticeRecommendation(BaseModel):
    id: str
    question_id: Optional[int]
    topic: str
    subtopic: Optional[str] = None
    difficulty: Literal["foundation", "consolidation", "exam-style"]
    title: str
    reason: str
    source_label: Optional[str] = None
    unavailable: bool = False
    trigger: Literal["auto", "ask_first", "unavailable"]
    paper_num: Optional[int] = None
    requires_confirmation: bool = False
    question: Optional[QuestionBankItem] = None


class PracticeRecommendationResponse(BaseModel):
    status: str = "success"
    recommendation_mode: PracticeRecommendationMode
    message: str
    detected_topic: Optional[str] = None
    detected_subtopic: Optional[str] = None
    paper_num: Optional[int] = None
    match_confidence: Optional[Literal["high", "medium", "low"]] = None
    recommendations: list[PracticeRecommendation] = Field(default_factory=list)


practice_orchestrator_router = APIRouter(
    prefix="/practice-orchestrator",
    tags=["practice-orchestrator"],
)


def normalise_paper_num(value: Optional[int]) -> Optional[int]:
    if value in SUPPORTED_PAPERS:
        return value
    return None


def _normalise_topic_key(value: object, paper_num: Optional[int]) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    lower = re.sub(r"[_-]+", " ", text.lower())
    lower = re.sub(r"\s+", " ", lower).strip()
    if lower in BROAD_TOPIC_BY_PAPER and paper_num in BROAD_TOPIC_BY_PAPER[lower]:
        return BROAD_TOPIC_BY_PAPER[lower][paper_num]
    if lower in TOPIC_ALIASES:
        return TOPIC_ALIASES[lower]
    snake = lower.replace(" ", "_")
    if snake:
        return snake
    return None


def derive_candidate_topics(req: PracticeRecommendationRequest) -> list[str]:
    paper_num = normalise_paper_num(req.context.paper_num)
    ordered: list[str] = []

    for item in req.priority_topics:
        for key in ("topic", "subtopic", "chapter"):
            topic = _normalise_topic_key(item.get(key), paper_num)
            if topic and topic not in ordered:
                ordered.append(topic)

    for key, _count in sorted(req.knowledge_tags_summary.items(), key=lambda kv: kv[1], reverse=True):
        topic = _normalise_topic_key(key, paper_num)
        if topic and topic not in ordered:
            ordered.append(topic)

    for question in req.questions:
        if question.is_correct or question.unanswered:
            continue
        for tag in question.knowledge_tags:
            topic = _normalise_topic_key(tag, paper_num)
            if topic and topic not in ordered:
                ordered.append(topic)
        topic = _normalise_topic_key(question.error_type, paper_num)
        if topic and topic not in ordered:
            ordered.append(topic)

    return ordered


def choose_recommendation_mode(
    context: PracticeRecommendationContext,
    *,
    has_topic: bool,
    has_review_risk: bool,
) -> PracticeRecommendationMode:
    if context.recommendation_mode in {"auto", "ask_first", "none"}:
        return context.recommendation_mode
    if not has_topic:
        return "none"
    if has_review_risk and not context.confirmed_by_user:
        return "ask_first"
    if context.confirmed_by_user:
        return "auto"
    if context.grading_route == "past_paper_mark_scheme":
        return "auto"
    if context.upload_intent in {"past_paper", "full_past_paper_pdf", "partial_past_paper_pages"}:
        return "auto" if context.match_confidence == "high" else "ask_first"
    if context.upload_intent in {"single_question_photo", "custom_homework", "unknown", "answer_pages_only"}:
        return "ask_first"
    return "none"


def _difficulty_slots(req: PracticeRecommendationRequest) -> list[tuple[str, str, int, int]]:
    if req.preferred_difficulty_min and req.preferred_difficulty_max:
        return [("adaptive", "下一题", req.preferred_difficulty_min, req.preferred_difficulty_max)]
    return [
        ("foundation", "基础修复", 1, 2),
        ("consolidation", "巩固练习", 3, 3),
        ("exam-style", "真题风格", 4, 5),
    ]


def _reason_for_slot(title: str, topic: str, scoped_to_paper: bool) -> str:
    scope = "同一套 paper 范围内" if scoped_to_paper else "按题型"
    if title == "基础修复":
        return f"本次暴露出 {topic} 的薄弱点，先用{scope}的低难度题补稳。"
    if title == "巩固练习":
        return f"继续练 {topic}，检查是否能独立完成完整步骤。"
    if title == "真题风格":
        return f"用更接近考试难度的题确认 {topic} 是否真的掌握。"
    return f"根据刚刚的作答结果，继续练 {topic}。"


def _query_recommendations(req: PracticeRecommendationRequest, topic: str) -> list[PracticeRecommendation]:
    paper_num = normalise_paper_num(req.context.paper_num)
    scoped_to_paper = paper_num is not None and (
        req.context.confirmed_by_user
        or req.context.grading_route == "past_paper_mark_scheme"
        or req.context.upload_intent in {"past_paper", "full_past_paper_pdf", "partial_past_paper_pages"}
    )
    paper_nums = [paper_num] if scoped_to_paper and paper_num else None
    exclude_ids = list(req.exclude_ids)
    recommendations: list[PracticeRecommendation] = []

    conn = ensure_db()
    try:
        for slot, title, difficulty_min, difficulty_max in _difficulty_slots(req):
            questions, _total = get_random_questions(
                conn,
                topics=[topic],
                difficulty_min=difficulty_min,
                difficulty_max=difficulty_max,
                count=1,
                paper_nums=paper_nums,
                exclude_ids=exclude_ids,
            )
            if not questions:
                continue
            question = questions[0]
            if question.id is not None:
                exclude_ids.append(question.id)
            recommendations.append(
                PracticeRecommendation(
                    id=f"{slot}-{question.id}",
                    question_id=question.id,
                    topic=question.topic,
                    subtopic=question.subtopic,
                    difficulty=slot if slot in {"foundation", "consolidation", "exam-style"} else "consolidation",
                    title=title,
                    reason=_reason_for_slot(title, topic, scoped_to_paper),
                    source_label="同 paper · 同 topic" if scoped_to_paper else "同 topic · 题库匹配",
                    trigger="auto",
                    paper_num=question.paper_num,
                    requires_confirmation=False,
                    question=question,
                )
            )
    finally:
        conn.close()

    return recommendations


@practice_orchestrator_router.post("/recommendations", response_model=PracticeRecommendationResponse)
async def recommend_practice(req: PracticeRecommendationRequest) -> PracticeRecommendationResponse:
    topics = derive_candidate_topics(req)
    topic = topics[0] if topics else None
    has_review_risk = any(q.needs_review for q in req.questions)
    mode = choose_recommendation_mode(req.context, has_topic=topic is not None, has_review_risk=has_review_risk)
    paper_num = normalise_paper_num(req.context.paper_num)

    if mode == "none" or topic is None:
        return PracticeRecommendationResponse(
            recommendation_mode="none",
            message="这次我还不能可靠地为你匹配练习题。建议先确认题目来源，或上传 Past Paper 封面/题目页。",
            detected_topic=topic,
            paper_num=paper_num,
            match_confidence=req.context.match_confidence,
            recommendations=[],
        )

    if mode == "ask_first":
        label = f"P{paper_num} " if paper_num else ""
        return PracticeRecommendationResponse(
            recommendation_mode="ask_first",
            message=f"我检测到这题像是 {label}{topic}。要不要再做 2-3 道类似题来确认这个点？",
            detected_topic=topic,
            paper_num=paper_num,
            match_confidence=req.context.match_confidence,
            recommendations=[],
        )

    recommendations = await run_in_threadpool(_query_recommendations, req, topic)
    if not recommendations:
        return PracticeRecommendationResponse(
            recommendation_mode="none",
            message=f"我找到了薄弱点 {topic}，但当前题库没有可用的真实候选题。",
            detected_topic=topic,
            paper_num=paper_num,
            match_confidence=req.context.match_confidence,
            recommendations=[],
        )

    return PracticeRecommendationResponse(
        recommendation_mode="auto",
        message="已根据本次批改结果推荐真实题库练习。",
        detected_topic=topic,
        paper_num=paper_num,
        match_confidence=req.context.match_confidence,
        recommendations=recommendations[: req.count],
    )
```

- [ ] **Step 4: Wire router**

Modify `api/app.py`:

```python
from api.practice_orchestrator import practice_orchestrator_router
```

Then add after `app.include_router(qb_router)`:

```python
app.include_router(practice_orchestrator_router)
```

- [ ] **Step 5: Run backend tests**

Run:

```bash
pytest test/test_practice_orchestrator.py test/test_paper_resolver.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add api/practice_orchestrator.py api/app.py test/test_practice_orchestrator.py
git commit -m "Add practice recommendation orchestrator API"
```

---

### Task 3: 前端 API Client 与上下文推导

**Role:** 前端子智能体 + 算法子智能体

**Files:**
- Create: `frontend/src/api/practiceOrchestrator.ts`
- Create: `frontend/src/lib/practiceRecommendationContext.ts`

- [ ] **Step 1: Create API client**

Create `frontend/src/api/practiceOrchestrator.ts`:

```ts
import type {
  PracticeRecommendationRequest,
  PracticeRecommendationResponse,
} from '../types/practice'

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/+$/, '') ?? ''

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const data = await res.json().catch(() => null)
    const msg = data?.detail ?? data?.message ?? `HTTP ${res.status}`
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
  }
  return res.json()
}

export async function recommendPractice(
  body: PracticeRecommendationRequest,
): Promise<PracticeRecommendationResponse> {
  const res = await fetch(`${API_BASE}/practice-orchestrator/recommendations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return handleResponse(res)
}
```

- [ ] **Step 2: Create context helper**

Create `frontend/src/lib/practiceRecommendationContext.ts`:

```ts
import type { AgentStepData } from '../api/client'
import type { AnalyzeRequest, PageSummary, QuestionResult, UploadIntent } from '../types'
import type {
  PracticeRecommendationContext,
  PracticeRecommendationRequest,
  PracticeRecommendationSourceQuestion,
  PracticeUploadIntent,
  SubmitAnswerResponse,
} from '../types/practice'

function toPracticeIntent(intent: UploadIntent | undefined): PracticeUploadIntent {
  return (intent ?? 'unknown') as PracticeUploadIntent
}

function parsePaperNumFromPaperCode(value?: string): 1 | 2 | 3 | 4 | 5 | 6 | null {
  const text = (value ?? '').trim()
  const match = text.match(/(?:^|\D)([1-6])[1-3](?:\D|$)/)
  if (!match) return null
  const paper = Number(match[1])
  return paper >= 1 && paper <= 6 ? (paper as 1 | 2 | 3 | 4 | 5 | 6) : null
}

function getResolutionStep(agentSteps: AgentStepData[]): AgentStepData | null {
  return [...agentSteps].reverse().find((step) => {
    return step.question_number === '本次上传' && (step.match_confidence || step.grading_route || step.detail)
  }) ?? null
}

function getPaperNumFromAgentStep(step: AgentStepData | null): 1 | 2 | 3 | 4 | 5 | 6 | null {
  const direct = step?.detail?.catalog_match
  if (direct && typeof direct === 'object' && 'paper_num' in direct) {
    const value = Number((direct as { paper_num?: unknown }).paper_num)
    if (value >= 1 && value <= 6) return value as 1 | 2 | 3 | 4 | 5 | 6
  }
  const paperId = typeof step?.paper_id === 'string' ? step.paper_id : ''
  const match = paperId.match(/_(?:m|s|w)\d{2}_([1-6])[1-3]/i)
  if (!match) return null
  return Number(match[1]) as 1 | 2 | 3 | 4 | 5 | 6
}

export function buildPracticeContext(
  request: AnalyzeRequest | null,
  agentSteps: AgentStepData[],
  confirmedByUser = false,
): PracticeRecommendationContext {
  const step = getResolutionStep(agentSteps)
  const paperNum = getPaperNumFromAgentStep(step) ?? parsePaperNumFromPaperCode(request?.paper_code)
  return {
    upload_intent: toPracticeIntent(request?.upload_intent),
    paper_num: paperNum,
    question_number: request?.question_numbers ?? null,
    match_confidence: step?.match_confidence ?? null,
    confirmed_by_user: confirmedByUser,
    grading_route: step?.grading_route ?? null,
  }
}

export function buildPracticeRequest(args: {
  request: AnalyzeRequest | null
  agentSteps: AgentStepData[]
  summary: PageSummary
  questions: QuestionResult[]
  excludeIds: number[]
  confirmedByUser?: boolean
  preferredDifficultyMin?: number
  preferredDifficultyMax?: number
}): PracticeRecommendationRequest {
  const sourceQuestions: PracticeRecommendationSourceQuestion[] = args.questions.map((q) => ({
    question_number: q.question_number,
    score: q.score,
    full_score: q.full_score,
    is_correct: q.is_correct,
    unanswered: q.unanswered,
    error_type: q.error_type,
    knowledge_tags: q.knowledge_tags ?? [],
    needs_review: q.needs_review,
  }))

  return {
    context: buildPracticeContext(args.request, args.agentSteps, args.confirmedByUser ?? false),
    priority_topics: args.summary.priority_topics ?? [],
    knowledge_tags_summary: args.summary.knowledge_tags_summary ?? {},
    questions: sourceQuestions,
    exclude_ids: args.excludeIds,
    preferred_difficulty_min: args.preferredDifficultyMin,
    preferred_difficulty_max: args.preferredDifficultyMax,
    count: 3,
  }
}

export function difficultyRangeFromPracticeResult(result: SubmitAnswerResponse): [number, number] {
  const full = result.grade_result.full_score || 0
  const score = result.grade_result.score || 0
  const rate = full > 0 ? score / full : 0
  if (result.grade_result.is_correct || rate >= 0.8) return [3, 5]
  if (rate >= 0.4) return [2, 3]
  return [1, 2]
}
```

- [ ] **Step 3: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS after Task 1 and Task 3 are both present.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/practiceOrchestrator.ts frontend/src/lib/practiceRecommendationContext.ts frontend/src/types/practice.ts
git commit -m "Add practice recommendation client helpers"
```

---

### Task 4: 结果页推荐组件

**Role:** 前端子智能体 + 产品子智能体

**Files:**
- Create: `frontend/src/components/practice/PracticeRecommendations.tsx`

- [ ] **Step 1: Create component**

Create `frontend/src/components/practice/PracticeRecommendations.tsx`:

```tsx
import { useCallback, useEffect, useMemo, useState } from 'react'
import type { AgentStepData } from '../../api/client'
import { recommendPractice } from '../../api/practiceOrchestrator'
import { submitAnswer } from '../../api/practice'
import type { AnalyzeRequest, PageSummary, QuestionResult } from '../../types'
import type {
  PracticeRecommendation,
  PracticeRecommendationResponse,
  SubmitAnswerResponse,
} from '../../types/practice'
import {
  buildPracticeRequest,
  difficultyRangeFromPracticeResult,
} from '../../lib/practiceRecommendationContext'
import { AnswerInput } from './AnswerInput'
import { PracticeQuestionCard } from './QuestionCard'
import { PracticeResult } from './PracticeResult'

interface Props {
  request: AnalyzeRequest | null
  agentSteps: AgentStepData[]
  summary: PageSummary | null
  questions: QuestionResult[]
  initialResponse?: PracticeRecommendationResponse
  loader?: typeof recommendPractice
  answerSubmitter?: typeof submitAnswer
}

function modeLabel(response: PracticeRecommendationResponse): string {
  if (response.recommendation_mode === 'auto') return '下一步练习'
  if (response.recommendation_mode === 'ask_first') return '要不要继续练这个点？'
  return '练习推荐暂不可用'
}

function nextActionText(result: SubmitAnswerResponse): string {
  const full = result.grade_result.full_score || 0
  const rate = full > 0 ? result.grade_result.score / full : 0
  if (result.grade_result.is_correct || rate >= 0.8) return '这题掌握不错，可以升一点难度。'
  if (rate >= 0.4) return '你已经拿到部分分数，建议继续做一道同主题中等难度题。'
  return '先回看讲解，再做一道更基础的同主题题。'
}

export function PracticeRecommendations({
  request,
  agentSteps,
  summary,
  questions,
  initialResponse,
  loader = recommendPractice,
  answerSubmitter = submitAnswer,
}: Props) {
  const [response, setResponse] = useState<PracticeRecommendationResponse | null>(initialResponse ?? null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [confirmed, setConfirmed] = useState(false)
  const [activeRecommendation, setActiveRecommendation] = useState<PracticeRecommendation | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [practiceResult, setPracticeResult] = useState<SubmitAnswerResponse | null>(null)
  const [recommendedIds, setRecommendedIds] = useState<number[]>([])
  const [completedIds, setCompletedIds] = useState<number[]>([])

  const canLoad = summary !== null && questions.length > 0

  const baseRequest = useMemo(() => {
    if (!summary) return null
    return buildPracticeRequest({
      request,
      agentSteps,
      summary,
      questions,
      excludeIds: [...recommendedIds, ...completedIds],
      confirmedByUser: confirmed,
    })
  }, [agentSteps, completedIds, confirmed, questions, recommendedIds, request, summary])

  const load = useCallback(async (forceConfirmed = false, preferredRange?: [number, number]) => {
    if (!summary) return
    setLoading(true)
    setError(null)
    try {
      const body = buildPracticeRequest({
        request,
        agentSteps,
        summary,
        questions,
        excludeIds: [...recommendedIds, ...completedIds],
        confirmedByUser: forceConfirmed || confirmed,
        preferredDifficultyMin: preferredRange?.[0],
        preferredDifficultyMax: preferredRange?.[1],
      })
      const next = await loader(body)
      setResponse(next)
      const ids = next.recommendations
        .map((item) => item.question_id)
        .filter((id): id is number => typeof id === 'number')
      setRecommendedIds((prev) => Array.from(new Set([...prev, ...ids])))
    } catch (e) {
      setError(e instanceof Error ? e.message : '获取练习推荐失败')
    } finally {
      setLoading(false)
    }
  }, [agentSteps, completedIds, confirmed, loader, questions, recommendedIds, request, summary])

  useEffect(() => {
    if (initialResponse || !canLoad || response || loading || !baseRequest) return
    void load(false)
  }, [baseRequest, canLoad, initialResponse, load, loading, response])

  const handleConfirmAskFirst = useCallback(() => {
    setConfirmed(true)
    void load(true)
  }, [load])

  const handleStart = useCallback((item: PracticeRecommendation) => {
    if (!item.question) return
    setPracticeResult(null)
    setActiveRecommendation(item)
  }, [])

  const handleSubmit = useCallback(async (answer: string, steps: string[]) => {
    const questionId = activeRecommendation?.question_id
    if (!questionId) return
    setSubmitting(true)
    setError(null)
    try {
      const result = await answerSubmitter({
        question_id: questionId,
        student_answer: answer,
        working_steps: steps,
      })
      setPracticeResult(result)
      setCompletedIds((prev) => Array.from(new Set([...prev, questionId])))
    } catch (e) {
      setError(e instanceof Error ? e.message : '提交练习答案失败')
    } finally {
      setSubmitting(false)
    }
  }, [activeRecommendation, answerSubmitter])

  const handleNextAdaptive = useCallback(() => {
    if (!practiceResult) return
    setActiveRecommendation(null)
    const range = difficultyRangeFromPracticeResult(practiceResult)
    void load(true, range)
  }, [load, practiceResult])

  if (!summary || questions.length === 0) return null

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-blue-700">Practice Loop</p>
          <h2 className="mt-1 text-lg font-semibold text-slate-950">
            {response ? modeLabel(response) : '正在判断下一步练习'}
          </h2>
          <p className="mt-1 text-sm leading-6 text-slate-600">
            {response?.message ?? '系统正在根据本次批改结果判断是否适合推荐真实题库练习。'}
          </p>
        </div>
        {response?.match_confidence ? (
          <span className="rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-600">
            识别置信度：{response.match_confidence === 'high' ? '高' : response.match_confidence === 'medium' ? '中' : '低'}
          </span>
        ) : null}
      </div>

      {error ? (
        <p className="mb-4 rounded-md border border-red-100 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
      ) : null}

      {loading ? (
        <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-4 text-sm text-slate-500">
          正在从题库匹配练习题...
        </div>
      ) : null}

      {response?.recommendation_mode === 'ask_first' ? (
        <div className="rounded-md border border-blue-100 bg-blue-50/70 p-4">
          <p className="text-sm font-medium text-slate-950">
            检测到：{response.paper_num ? `P${response.paper_num} · ` : ''}{response.detected_topic ?? '相似题型'}
          </p>
          <p className="mt-1 text-sm leading-6 text-slate-600">{response.message}</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={handleConfirmAskFirst}
              className="rounded-md bg-slate-950 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-800"
            >
              给我 2-3 道类似题
            </button>
            <button
              type="button"
              onClick={() => setResponse({ ...response, recommendation_mode: 'none', message: '已保留本次批改反馈，暂不进入练习。' })}
              className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
            >
              暂时不用
            </button>
          </div>
        </div>
      ) : null}

      {response?.recommendation_mode === 'none' ? (
        <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-4 text-sm leading-6 text-slate-600">
          {response.message}
        </div>
      ) : null}

      {response?.recommendations.length ? (
        <div className="grid gap-3 md:grid-cols-3">
          {response.recommendations.map((item) => (
            <article key={item.id} className="rounded-md border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold text-slate-950">{item.title}</p>
                  <p className="mt-1 text-xs text-slate-500">{item.source_label}</p>
                </div>
                <span className="rounded-md bg-white px-2 py-1 text-xs font-medium text-slate-600 ring-1 ring-slate-200">
                  {item.difficulty}
                </span>
              </div>
              <p className="mt-3 text-sm leading-6 text-slate-600">{item.reason}</p>
              <button
                type="button"
                onClick={() => handleStart(item)}
                disabled={!item.question}
                className="mt-4 w-full rounded-md bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                开始练习
              </button>
            </article>
          ))}
        </div>
      ) : null}

      {activeRecommendation?.question ? (
        <div className="mt-5 border-t border-slate-100 pt-5">
          <PracticeQuestionCard question={activeRecommendation.question} index={0} total={1}>
            {!practiceResult ? (
              <AnswerInput onSubmit={handleSubmit} submitting={submitting} disabled={false} />
            ) : (
              <>
                <PracticeResult result={practiceResult} />
                <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3">
                  <p className="text-sm text-slate-700">{nextActionText(practiceResult)}</p>
                  <button
                    type="button"
                    onClick={handleNextAdaptive}
                    className="mt-3 rounded-md bg-slate-950 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-800"
                  >
                    调整下一题
                  </button>
                </div>
              </>
            )}
          </PracticeQuestionCard>
        </div>
      ) : null}
    </section>
  )
}
```

- [ ] **Step 2: Run build**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/practice/PracticeRecommendations.tsx
git commit -m "Add practice recommendations panel"
```

---

### Task 5: 接入批改结果页

**Role:** 前端子智能体

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Add import**

Modify the imports in `frontend/src/App.tsx`:

```ts
import { PracticeRecommendations } from './components/practice/PracticeRecommendations'
```

- [ ] **Step 2: Persist last analyze request**

Inside `App`, near other state:

```ts
const [lastAnalyzeRequest, setLastAnalyzeRequest] = useState<AnalyzeRequest | null>(null)
```

In `handleResetUpload`, add:

```ts
setLastAnalyzeRequest(null)
```

At the start of `handleSubmit`, after creating `newUrls`, add:

```ts
setLastAnalyzeRequest(req)
```

- [ ] **Step 3: Render recommendations after PageSummary**

Replace:

```tsx
{showSummaryBlock ? <PageSummary summary={summary} /> : null}
```

with:

```tsx
{showSummaryBlock ? (
  <>
    <PageSummary summary={summary} />
    <PracticeRecommendations
      request={lastAnalyzeRequest}
      agentSteps={agentSteps}
      summary={summary}
      questions={questions}
    />
  </>
) : null}
```

- [ ] **Step 4: Run build**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "Show practice loop after grading summary"
```

---

### Task 6: Replay 页面与静态检查

**Role:** 前端子智能体 + 测试子智能体

**Files:**
- Create: `frontend/src/pages/PracticeRecommendationsReplayPage.tsx`
- Modify: `frontend/src/main.tsx`
- Create: `frontend/scripts/replay-practice-orchestrator.mjs`
- Modify: `frontend/package.json`

- [ ] **Step 1: Create replay page**

Create `frontend/src/pages/PracticeRecommendationsReplayPage.tsx`:

```tsx
import { PracticeRecommendations } from '../components/practice/PracticeRecommendations'
import {
  askFirstRecommendationFixture,
  autoRecommendationFixture,
  practiceReplayQuestions,
  practiceReplaySummary,
  unavailableRecommendationFixture,
} from '../fixtures/practiceOrchestratorReplay'

export function PracticeRecommendationsReplayPage() {
  return (
    <main className="min-h-screen bg-slate-100 px-4 py-6 text-slate-950">
      <div className="mx-auto max-w-6xl space-y-5">
        <header>
          <p className="text-xs font-semibold uppercase tracking-wide text-blue-700">Replay</p>
          <h1 className="mt-1 text-xl font-semibold">Practice Recommendations Replay</h1>
        </header>
        <PracticeRecommendations
          request={{ images: [], upload_intent: 'past_paper', paper_code: '9709/12/M/J/24' }}
          agentSteps={[]}
          summary={practiceReplaySummary}
          questions={practiceReplayQuestions}
          initialResponse={autoRecommendationFixture}
          loader={async () => autoRecommendationFixture}
          answerSubmitter={async () => ({
            status: 'success',
            question_id: 101,
            grade_result: {
              is_correct: true,
              score: 4,
              full_score: 4,
              error_type: null,
              short_feedback: '完整写出了两个根，步骤清楚。',
              knowledge_tags: ['quadratics'],
              student_feedback: '这次你补上了完整解集。',
            },
            reference_answer: '\\(x = 3\\) or \\(x = -\\frac{1}{2}\\)',
            marking_points: ['factorise', 'state both roots'],
            source: { year: 2024, session: 's', paper: 1, variant: 2, question_number: '5' },
          })}
        />
        <PracticeRecommendations
          request={{ images: [], upload_intent: 'custom_homework' }}
          agentSteps={[]}
          summary={practiceReplaySummary}
          questions={practiceReplayQuestions}
          initialResponse={askFirstRecommendationFixture}
          loader={async () => autoRecommendationFixture}
        />
        <PracticeRecommendations
          request={{ images: [], upload_intent: 'unknown' }}
          agentSteps={[]}
          summary={practiceReplaySummary}
          questions={practiceReplayQuestions}
          initialResponse={unavailableRecommendationFixture}
          loader={async () => unavailableRecommendationFixture}
        />
      </div>
    </main>
  )
}
```

- [ ] **Step 2: Add route**

Modify `frontend/src/main.tsx` imports:

```ts
import { PracticeRecommendationsReplayPage } from './pages/PracticeRecommendationsReplayPage.tsx'
```

Add a dev route:

```tsx
{import.meta.env.DEV ? (
  <Route path="/__practice-recommendations-replay" element={<PracticeRecommendationsReplayPage />} />
) : null}
```

- [ ] **Step 3: Create static replay check**

Create `frontend/scripts/replay-practice-orchestrator.mjs`:

```js
import { readFile } from 'node:fs/promises'

const root = new URL('../', import.meta.url)
const component = await readFile(new URL('src/components/practice/PracticeRecommendations.tsx', root), 'utf8')
const fixture = await readFile(new URL('src/fixtures/practiceOrchestratorReplay.ts', root), 'utf8')

for (const snippet of ['下一步练习', '要不要继续练这个点', '给我 2-3 道类似题', '调整下一题']) {
  if (!component.includes(snippet)) {
    throw new Error(`PracticeRecommendations missing expected student-facing snippet: ${snippet}`)
  }
}

for (const raw of ['>think<', '>act<', '>observe<', '>decide<', '>final<']) {
  if (component.toLowerCase().includes(raw)) {
    throw new Error(`Raw agent label leaked into practice UI: ${raw}`)
  }
}

for (const mode of ['auto', 'ask_first', 'none']) {
  if (!fixture.includes(`recommendation_mode: '${mode}'`)) {
    throw new Error(`Replay fixture missing mode: ${mode}`)
  }
}

console.log(JSON.stringify({ status: 'ok', checked: 'practice-orchestrator-replay' }, null, 2))
```

- [ ] **Step 4: Add npm script**

Modify `frontend/package.json` scripts:

```json
"test:practice-orchestrator": "node scripts/replay-practice-orchestrator.mjs"
```

- [ ] **Step 5: Run checks**

Run:

```bash
cd frontend && npm run test:practice-orchestrator && npm run build
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/PracticeRecommendationsReplayPage.tsx frontend/src/main.tsx frontend/scripts/replay-practice-orchestrator.mjs frontend/package.json
git commit -m "Add practice recommendation replay coverage"
```

---

### Task 7: End-to-end verification

**Role:** 测试子智能体 + 主智能体

**Files:**
- No planned source changes unless verification finds a bug.

- [ ] **Step 1: Run backend tests**

Run:

```bash
pytest test/test_practice_orchestrator.py test/test_paper_resolver.py test/test_large_pdf_mode.py -q
```

Expected: PASS.

- [ ] **Step 2: Run frontend checks**

Run:

```bash
cd frontend && npm run test:practice-orchestrator && npm run build
```

Expected: PASS.

- [ ] **Step 3: Run focused lint on touched files**

Run:

```bash
cd frontend && npx eslint src/components/practice/PracticeRecommendations.tsx src/pages/PracticeRecommendationsReplayPage.tsx src/api/practiceOrchestrator.ts src/lib/practiceRecommendationContext.ts src/types/practice.ts src/main.tsx src/App.tsx
```

Expected: PASS. If full `npm run lint` still fails in unrelated legacy files, report those paths separately and do not mix them into this feature.

- [ ] **Step 4: Capture real browser evidence**

Run:

```bash
node scripts/visual_acceptance.mjs --path /__practice-recommendations-replay --out /private/tmp/alevel-practice-orchestrator-visual --server-port 3031 --skip-content-checks
```

Expected:

- `/private/tmp/alevel-practice-orchestrator-visual/desktop.png` exists.
- `/private/tmp/alevel-practice-orchestrator-visual/mobile.png` exists.
- The screenshots show auto recommendation, ask-first card, and unavailable fallback.
- There is no horizontal overflow on mobile.

- [ ] **Step 5: Manual smoke test**

Start backend and frontend if they are not already running:

```bash
python server.py
cd frontend && npm run dev -- --host 127.0.0.1 --port 3025
```

Open `http://127.0.0.1:3025/__practice-recommendations-replay`.

Expected:

- Auto card shows at least one real recommendation card.
- Ask-first card asks before showing questions.
- Unavailable card says why no question is recommended.
- Starting a recommendation opens an inline question panel.
- Submitting a fixture answer shows `PracticeResult`.

- [ ] **Step 6: Final commit if verification required fixes**

If verification fixes were needed:

```bash
git add api/practice_orchestrator.py api/app.py test/test_practice_orchestrator.py frontend/src
git commit -m "Polish practice orchestrator verification"
```

If no fixes were needed, do not create an empty commit.

---

## Self-Review Checklist

- Spec coverage: automatic Past Paper recommendation is implemented by `choose_recommendation_mode` and the backend endpoint.
- Spec coverage: single-question and custom-homework flows are implemented by `ask_first` mode.
- Spec coverage: P1-P6 boundary is implemented by `normalise_paper_num`.
- Spec coverage: no fake recommendations is implemented by returning `none` when there are no topics or no real question candidates.
- Spec coverage: inline practice is implemented by `PracticeRecommendations` reusing `AnswerInput` and `PracticeResult`.
- Spec coverage: adaptive next action is implemented by `difficultyRangeFromPracticeResult`.
- Product copy avoids raw `think / act / observe / decide / final` labels.
- Tests include backend unit checks, frontend static replay check, TypeScript build, focused lint, and real browser screenshots.
