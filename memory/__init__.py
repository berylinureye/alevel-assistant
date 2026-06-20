"""User Memory · 跨 session 持久化学生薄弱点 / 偏好 / 进度 / 目标

v1.5 升级：让 agent 知道这学生反复在哪栽 → 个性化推荐 + 主动提醒。

设计原则（跟杜妲颐量子位访谈"长期记忆是下一代 AI 产品基础设施"对齐）：
- Mem0 风格 Fact Extraction（抽离散事实，不是存原始 chat log）
- 4 类 fact：weakness / preference / progress / goal
- Conflict Resolution：旧 fact 不直接覆盖，confidence × 0.5 decay，新旧并存
- Privacy：每个 fact 可查询/删除/导出（GDPR 友好）
"""
from memory.store import MemoryStore, StudentFact, FactType
from memory.extractor import extract_facts_from_session

__all__ = ["MemoryStore", "StudentFact", "FactType", "extract_facts_from_session"]
