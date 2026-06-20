"""Reflection Loop · 学生答错后苏格拉底式追问 + Memory 触发主动推相似题

v1.5 升级：从"被动答疑"升级到"主动陪伴"——
- 学生明确说"我不会" → 反问"你卡在哪一步"
- 学生跳步骤 → 引导回顾
- Memory 检测反复栽 → 主动推相似题练习

跟 wechat MCP 不同：这里"反问"是产品特性而不是 bug。

设计原则：
- 不替代 grader：grader 该给的反馈照给，reflection 是 wrap 一层
- 可关闭：用户可设置 reflection_mode = direct（直接给答案）/ socratic（苏格拉底）
- 跟 Memory 协同：reflection 用 memory 做个性化推荐
"""
from reflection.engine import (
    ReflectionEngine,
    ReflectionTrigger,
    ReflectionMode,
    detect_trigger,
)

__all__ = [
    "ReflectionEngine",
    "ReflectionTrigger",
    "ReflectionMode",
    "detect_trigger",
]
