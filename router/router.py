"""
Router：RouteContext → RouteDecision

逻辑：遍历所有规则，任一触发即升级到 review_model。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from router.context import RouteContext
from router.models import ModelRole
from router.rules import ESCALATION_RULES


@dataclass
class RouteDecision:
    role:      ModelRole
    reasons:   list[str] = field(default_factory=list)
    escalated: bool = False


def route(ctx: RouteContext) -> RouteDecision:
    reasons: list[str] = []
    for rule in ESCALATION_RULES:
        triggered, reason = rule(ctx)
        if triggered:
            reasons.append(reason)

    if reasons:
        return RouteDecision(role=ModelRole.review, reasons=reasons, escalated=True)
    return RouteDecision(role=ModelRole.base, reasons=[], escalated=False)
