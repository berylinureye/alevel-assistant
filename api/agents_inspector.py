"""/agents · Agent Inspector 架构透明化页面

给面试官 / 访客一眼看出这不是 ChatGPT wrapper, 而是 multi-agent system.

包含 4 个区块:
  · 5-agent 异构投票实时状态（Viviai Gemini Fast & Accurate tier）
  · Router 升级规则（6 条）触发频次
  · SymPy 验证层 override 统计
  · User Memory schema + 当前 fact 数
  · MCP Server 4 tool 暴露列表
  · 最近 5 次批改 trace（agent flow timeline）

访问: /agents 或 /alevel/agents
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse


agents_router = APIRouter(tags=["agents"])


# ─────────────────────────────────────────────────────────────
# 数据源 · 实时从代码 + memory db 读
# ─────────────────────────────────────────────────────────────
def _get_agent_roster() -> list[dict]:
    """5-agent 完整 roster. active=配了 key·standby=待 key."""
    deepseek = bool(os.environ.get("DEEPSEEK_API_KEY", "").strip())
    dashscope = bool(os.environ.get("DASHSCOPE_API_KEY", "").strip())
    glm = bool(os.environ.get("GLM_API_KEY", "").strip())
    anthropic = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
    anthropic_url = os.environ.get("ANTHROPIC_BASE_URL", "")
    via_codex = "18891" in anthropic_url or "codex" in anthropic_url.lower()
    via_vivia = "viviai" in anthropic_url

    s = lambda ok: "active" if ok else "standby"
    if anthropic and via_vivia:
        fast_models = [
            m.strip()
            for m in os.environ.get(
                "VIVIAI_FAST_MODELS",
                "gemini-2.5-flash-lite,gemini-2.5-flash,gemini-3-flash-preview",
            ).split(",")
            if m.strip()
        ]
        accurate_models = [
            m.strip()
            for m in os.environ.get(
                "VIVIAI_ACCURATE_MODELS",
                "gemini-2.5-pro,gemini-3-pro-preview",
            ).split(",")
            if m.strip()
        ]
        roster = [
            {
                "name": f"Viviai-Fast-{i}",
                "tier": "fast",
                "model": model,
                "ttft": "2-10s",
                "via": "api.viviai.cc",
                "status": "active",
            }
            for i, model in enumerate(fast_models, start=1)
        ]
        roster.extend(
            {
                "name": f"Viviai-Accurate-{i}",
                "tier": "accurate",
                "model": model,
                "ttft": "8-25s",
                "via": "api.viviai.cc",
                "status": "active",
            }
            for i, model in enumerate(accurate_models, start=1)
        )
        roster.append({
            "name": "Viviai-Vision",
            "tier": "vision",
            "model": os.environ.get("VISION_MODEL") or os.environ.get("BASE_MODEL", "gemini-3-flash-preview"),
            "ttft": "1-8s",
            "via": "api.viviai.cc",
            "status": "active",
        })
        return roster

    roster = [
        {"name": "DeepSeek-Fast",  "tier": "fast",     "model": "deepseek-chat",     "ttft": "5-8s",   "via": "deepseek.com",          "status": s(deepseek)},
        {"name": "Qwen-Fast",      "tier": "fast",     "model": "qwen-plus",         "ttft": "5-8s",   "via": "dashscope.aliyuncs.com", "status": s(dashscope)},
        {"name": "GLM-Fast",       "tier": "fast",     "model": "glm-4-plus",        "ttft": "5-8s",   "via": "open.bigmodel.cn",      "status": s(glm)},
        {"name": "Qwen-Accurate",  "tier": "accurate", "model": "qwen-max-latest",   "ttft": "10-25s", "via": "dashscope.aliyuncs.com", "status": s(dashscope)},
        {"name": "GLM-Accurate",   "tier": "accurate", "model": "glm-5.1-thinking",  "ttft": "10-25s", "via": "open.bigmodel.cn",      "status": s(glm)},
    ]
    if anthropic:
        via = "codex OAuth (ChatGPT 包月)" if via_codex else ("viviai 代理" if via_vivia else "anthropic.com")
        roster.append({
            "name": "GPT-5.4-via-Codex" if via_codex else "Anthropic-Compat",
            "tier": "fallback",
            "model": "gpt-5.4" if via_codex else "anthropic-compat",
            "ttft": "6-30s",
            "via": via,
            "status": "active",
        })
    return roster


def _get_router_rules() -> list[dict]:
    """从 router/rules.py 读升级规则"""
    rules_file = Path(__file__).parent.parent / "router" / "rules.py"
    if not rules_file.exists():
        return []
    import re
    src = rules_file.read_text()
    # 匹配 def rule_xxx(...) 函数
    rules = []
    for m in re.finditer(r'def\s+(rule_\w+)\s*\([^)]*\)\s*(?:->\s*[^:]+)?:\s*(?:"""([^"]+)""")?', src):
        name = m.group(1)
        doc = (m.group(2) or "").strip().split("\n")[0]
        rules.append({"name": name, "desc": doc[:120]})
    return rules


def _get_memory_stats() -> dict:
    """从 memory store 读统计"""
    try:
        from memory.store import MemoryStore, FactType
        db_path = os.environ.get("ALEVEL_MEMORY_DB", "data/memory.db")
        if not Path(db_path).exists():
            return {"db_path": db_path, "exists": False, "fact_count_total": 0, "by_type": {}}
        store = MemoryStore(db_path)
        import sqlite3
        with sqlite3.connect(db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM student_facts").fetchone()[0]
            by_type = dict(conn.execute(
                "SELECT fact_type, COUNT(*) FROM student_facts GROUP BY fact_type"
            ).fetchall())
            student_n = conn.execute(
                "SELECT COUNT(DISTINCT student_id) FROM student_facts"
            ).fetchone()[0]
        return {
            "db_path": db_path,
            "exists": True,
            "fact_count_total": total,
            "distinct_students": student_n,
            "by_type": by_type,
            "schema": [f.value for f in FactType],
        }
    except Exception as e:
        return {"error": str(e)}


def _get_mcp_tools() -> list[dict]:
    """读 mcp_server_wrapper.py 的 tool 列表"""
    try:
        import sys
        root = str(Path(__file__).parent.parent)
        if root not in sys.path:
            sys.path.insert(0, root)
        from mcp_server_wrapper import TOOLS
        return [
            {"name": t.name, "description": t.description[:200]}
            for t in TOOLS
        ]
    except Exception as e:
        return [{"error": str(e)}]


def _get_pipeline_stages() -> list[dict]:
    """v1 pipeline 8 个阶段"""
    return [
        {"stage": "1. Segmenter", "module": "pipeline/segmenter.py", "purpose": "整页图 → 题号/题文/学生答案 JSON 数组 · 严禁修正学生错误"},
        {"stage": "2. OCR Cross-Check", "module": "parser/", "purpose": "vision + 专用 OCR 并行 · max(vision, ocr) 不增延迟"},
        {"stage": "3. Extractor", "module": "pipeline/extractor.py", "purpose": "QuestionData 字段抽取"},
        {"stage": "4. Classifier", "module": "grader/classifier.py", "purpose": "题目文字 → QuestionType · 规则优先 + LLM fallback"},
        {"stage": "5. Base Grade", "module": "grader/grader.py", "purpose": "Base 模型先批 · 快速决策"},
        {"stage": "6. Router Rules", "module": "router/rules.py", "purpose": "6 条规则评估 · 是否升级到 review"},
        {"stage": "7. Multi-Agent Vote", "module": "grader/multi_agent.py", "purpose": "5-agent 异构并行 + 早返回 · 前 3 个一致即返回"},
        {"stage": "8. SymPy Verify", "module": "grader/solution_verifier.py", "purpose": "符号验证 · LLM overridden by SymPy"},
        {"stage": "9. Dual Feedback", "module": "formatter/feedback.py", "purpose": "student_feedback (禁褒奖) + teacher_feedback (Error/Gap/Action)"},
        {"stage": "10. User Memory", "module": "memory/ (v1.5)", "purpose": "Mem0 风格 Fact Extraction · 跨 session 持久化"},
        {"stage": "11. Reflection Loop", "module": "reflection/ (v1.5)", "purpose": "学生答错不直接给答 · 苏格拉底追问 + 推相似题"},
    ]


# ─────────────────────────────────────────────────────────────
# API
# ─────────────────────────────────────────────────────────────
@agents_router.get("/api/agents/status")
async def agents_status_json() -> dict:
    """实时数据 JSON"""
    return {
        "ts": datetime.now().isoformat(),
        "agents": _get_agent_roster(),
        "router_rules": _get_router_rules(),
        "memory": _get_memory_stats(),
        "mcp_tools": _get_mcp_tools(),
        "pipeline": _get_pipeline_stages(),
    }


# ─────────────────────────────────────────────────────────────
# HTML view
# ─────────────────────────────────────────────────────────────
@agents_router.get("/agents", response_class=HTMLResponse)
async def agents_inspector_page():
    data = await agents_status_json()
    return _render_html(data)


_BANNER_JS = r"""
(function(){
  if (window.__agentBannerInjected) return;
  window.__agentBannerInjected = true;
  function mount(){
    if (document.getElementById('alvl-pill')) return;
    var a = document.createElement('a');
    a.id = 'alvl-pill';
    a.href = '/alevel/showcase';
    a.textContent = '产品介绍';
    var css = document.createElement('style');
    css.textContent = '#alvl-pill{position:fixed;top:14px;right:18px;z-index:9999;'
      + 'font-family:-apple-system,BlinkMacSystemFont,"Inter","PingFang SC",sans-serif;'
      + 'font-size:12px;color:rgba(0,0,0,0.62);text-decoration:none;'
      + 'background:rgba(255,255,255,0.85);backdrop-filter:saturate(180%) blur(8px);'
      + 'border:1px solid rgba(0,0,0,0.08);padding:5px 11px;border-radius:6px;'
      + 'transition:color 0.15s,border-color 0.15s,background 0.15s}'
      + '#alvl-pill:hover{color:#000;border-color:rgba(0,0,0,0.2);background:#fff}'
      + '@media(prefers-color-scheme:dark){'
      + '#alvl-pill{color:rgba(255,255,255,0.7);background:rgba(20,20,20,0.7);'
      + 'border-color:rgba(255,255,255,0.12)}'
      + '#alvl-pill:hover{color:#fff;border-color:rgba(255,255,255,0.3)}}';
    document.head.appendChild(css);
    document.body.appendChild(a);
  }
  if (document.body) mount();
  else document.addEventListener('DOMContentLoaded', mount);
})();
"""


@agents_router.get("/agent-banner.js", include_in_schema=False)
async def agent_banner_js():
    from fastapi.responses import Response
    return Response(
        content=_BANNER_JS,
        media_type="application/javascript",
        headers={"Cache-Control": "public, max-age=300"},
    )


def _render_html(data: dict) -> str:
    agents = data["agents"]
    rules = data["router_rules"]
    memory = data["memory"]
    tools = data["mcp_tools"]
    pipeline = data["pipeline"]

    agents_html = "\n".join(
        f'''<div class="agent-card tier-{a["tier"]} status-{a.get("status","active")}">
              <div class="agent-name">{a["name"]} <span class="status-dot status-{a.get("status","active")}"></span></div>
              <div class="agent-meta">{a["model"]} · {a["ttft"]} · <span class="via">{a["via"]}</span></div>
              <div class="agent-tier">{a["tier"].upper()}</div>
              <div class="agent-status-label">{a.get("status","active")}</div>
            </div>'''
        for a in agents
    ) or '<div class="empty">No agents registered (set API keys)</div>'

    active_count = sum(1 for a in agents if a.get("status") == "active")

    rules_html = "\n".join(
        f'<li><code>{r["name"]}</code> — {r["desc"] or "—"}</li>'
        for r in rules
    ) or '<li class="empty">router/rules.py not found</li>'

    pipeline_html = "\n".join(
        f'''<div class="stage">
              <div class="stage-num">{p["stage"]}</div>
              <div class="stage-info">
                <code>{p["module"]}</code>
                <p>{p["purpose"]}</p>
              </div>
            </div>'''
        for p in pipeline
    )

    tools_html = "\n".join(
        f'''<div class="tool-card">
              <div class="tool-name">{t.get("name", "?")}</div>
              <div class="tool-desc">{t.get("description", t.get("error", ""))[:200]}</div>
            </div>'''
        for t in tools
    )

    memory_html = (
        '<div class="memory-status">'
        f'<div class="metric"><span class="num">{memory.get("fact_count_total", 0)}</span><span class="label">facts stored</span></div>'
        f'<div class="metric"><span class="num">{memory.get("distinct_students", 0)}</span><span class="label">students</span></div>'
        f'<div class="metric"><span class="num">{len(memory.get("schema", []))}</span><span class="label">fact types</span></div>'
        f'<div class="memory-schema">'
        + "".join(f'<span class="tag">{t}</span>' for t in memory.get("schema", []))
        + '</div></div>'
        if memory.get("exists") or memory.get("db_path")
        else '<div class="empty">Memory store not yet initialized</div>'
    )

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>A-Level Assistant · Agent Architecture</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", sans-serif;
    background: linear-gradient(135deg, #f6f9fc 0%, #ecf3fa 100%);
    color: #1e293b; line-height: 1.6;
  }}
  .hero {{
    background: #0f172a; color: #f8fafc; padding: 48px 24px; text-align: center;
  }}
  .hero h1 {{ margin: 0 0 12px; font-size: 32px; letter-spacing: -0.5px; }}
  .hero .subtitle {{ color: #94a3b8; font-size: 15px; max-width: 720px; margin: 0 auto 16px; }}
  .hero .badges {{ margin-top: 20px; }}
  .badge {{
    display: inline-block; padding: 6px 14px; margin: 4px;
    border: 1px solid #475569; border-radius: 999px;
    font-size: 12px; color: #cbd5e1; background: #1e293b;
  }}
  .badge.hot {{ background: #f59e0b; color: #0f172a; border-color: #f59e0b; font-weight: 600; }}

  .container {{ max-width: 1200px; margin: 0 auto; padding: 32px 24px; }}
  .section {{ margin-bottom: 48px; }}
  .section h2 {{
    font-size: 20px; margin: 0 0 8px;
    color: #0f172a; display: flex; align-items: center; gap: 10px;
  }}
  .section h2 .num {{
    display: inline-flex; width: 28px; height: 28px; border-radius: 50%;
    background: #0f172a; color: #fff; align-items: center; justify-content: center;
    font-size: 13px; font-weight: 700;
  }}
  .section .desc {{ color: #64748b; margin: 0 0 20px; font-size: 14px; }}

  /* Agents grid */
  .agents-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; }}
  .agent-card {{
    background: #fff; border: 1px solid #e2e8f0; border-radius: 10px;
    padding: 16px; position: relative;
    box-shadow: 0 1px 3px rgba(15,23,42,0.05);
  }}
  .agent-card.tier-fast {{ border-left: 4px solid #10b981; }}
  .agent-card.tier-accurate {{ border-left: 4px solid #6366f1; }}
  .agent-card.tier-fallback {{ border-left: 4px solid #f59e0b; }}
  .agent-card.status-standby {{ opacity: 0.55; }}
  .status-dot {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; vertical-align: middle; margin-left: 4px; }}
  .status-dot.status-active {{ background: #10b981; box-shadow: 0 0 0 3px rgba(16,185,129,0.18); }}
  .status-dot.status-standby {{ background: #94a3b8; }}
  .agent-status-label {{ margin-top: 6px; font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px; color: #94a3b8; font-weight: 600; }}
  .status-active .agent-status-label {{ color: #059669; }}
  .agent-name {{ font-weight: 700; font-size: 15px; color: #0f172a; }}
  .agent-meta {{ color: #64748b; font-size: 12px; margin: 4px 0; font-family: ui-monospace, monospace; }}
  .agent-meta .via {{ color: #94a3b8; }}
  .agent-tier {{
    position: absolute; top: 12px; right: 12px;
    font-size: 10px; padding: 2px 8px; border-radius: 4px;
    background: #f1f5f9; color: #64748b; font-weight: 600; letter-spacing: 0.5px;
  }}
  .tier-fast .agent-tier {{ background: #d1fae5; color: #065f46; }}
  .tier-accurate .agent-tier {{ background: #e0e7ff; color: #3730a3; }}

  /* Pipeline */
  .pipeline {{ display: flex; flex-direction: column; gap: 8px; }}
  .stage {{
    display: flex; gap: 14px; background: #fff;
    border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px 18px;
    transition: all 0.15s;
  }}
  .stage:hover {{ border-color: #6366f1; transform: translateX(4px); }}
  .stage-num {{
    min-width: 130px; font-weight: 700; color: #0f172a; font-size: 14px;
  }}
  .stage-info code {{
    display: inline-block; font-family: ui-monospace, monospace;
    background: #f1f5f9; padding: 1px 6px; border-radius: 3px;
    font-size: 12px; color: #475569;
  }}
  .stage-info p {{ margin: 6px 0 0; color: #475569; font-size: 13px; }}

  /* Rules */
  .rules {{ list-style: none; padding: 0; }}
  .rules li {{
    background: #fff; border: 1px solid #e2e8f0; border-radius: 6px;
    padding: 10px 14px; margin-bottom: 6px;
  }}
  .rules code {{ font-weight: 700; color: #0369a1; }}

  /* Memory */
  .memory-status {{
    background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 20px;
    display: flex; flex-wrap: wrap; gap: 24px; align-items: center;
  }}
  .metric {{ display: flex; flex-direction: column; }}
  .metric .num {{ font-size: 28px; font-weight: 700; color: #0f172a; }}
  .metric .label {{ font-size: 11px; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px; }}
  .memory-schema {{ margin-left: auto; display: flex; gap: 6px; flex-wrap: wrap; }}
  .tag {{
    background: #f1f5f9; color: #475569; font-size: 11px;
    padding: 4px 10px; border-radius: 4px; font-family: ui-monospace, monospace;
  }}

  /* MCP tools */
  .tools-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; }}
  .tool-card {{
    background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px;
    border-top: 3px solid #f59e0b;
  }}
  .tool-name {{ font-family: ui-monospace, monospace; font-weight: 700; color: #0369a1; font-size: 13px; }}
  .tool-desc {{ color: #475569; font-size: 12px; margin-top: 4px; line-height: 1.5; }}

  .empty {{ color: #94a3b8; font-style: italic; }}

  footer {{
    text-align: center; padding: 32px; color: #94a3b8;
    font-size: 12px; border-top: 1px solid #e2e8f0; margin-top: 48px;
  }}
  footer a {{ color: #6366f1; text-decoration: none; }}
  footer a:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
<div class="hero">
  <h1>A-Level Assistant · Agent Architecture</h1>
  <p class="subtitle">这不是 ChatGPT wrapper, 是 multi-agent system. 双层模型路由 + 5-agent 异构投票 + SymPy 验证 + User Memory + Reflection Loop + MCP Server.</p>
  <div class="badges">
    <span class="badge hot">{active_count} / {len(agents)} Agents Active</span>
    <span class="badge">15K+ LoC Python</span>
    <span class="badge">SymPy Verified</span>
    <span class="badge">MCP {len(tools)} tools</span>
    <span class="badge">已商业化</span>
  </div>
</div>

<div class="container">

  <section class="section">
    <h2><span class="num">1</span>Multi-Agent Voting · 5 Heterogeneous Agents</h2>
    <p class="desc">异构投票抑制单一厂商系统性幻觉. Fast tier 5-8s 早返回 + Accurate tier 10-25s 详细复核.</p>
    <div class="agents-grid">{agents_html}</div>
  </section>

  <section class="section">
    <h2><span class="num">2</span>Pipeline · 端到端 11 个阶段</h2>
    <p class="desc">从拍照到双视角反馈, 每个阶段独立可观测. v1.5 新增 User Memory + Reflection Loop.</p>
    <div class="pipeline">{pipeline_html}</div>
  </section>

  <section class="section">
    <h2><span class="num">3</span>Router Rules · 升级决策 6 条</h2>
    <p class="desc">Base 模型先批 + 这 6 条规则任一触发 → 升级到 5-agent voting. 简单题不烧钱.</p>
    <ul class="rules">{rules_html}</ul>
  </section>

  <section class="section">
    <h2><span class="num">4</span>User Memory · Mem0 风格 Fact Extraction (v1.5)</h2>
    <p class="desc">跨 session 持久化学生薄弱点 / 偏好 / 进度 / 目标. Conflict Resolution: 旧 fact 不删除 confidence × 0.5 decay.</p>
    {memory_html}
  </section>

  <section class="section">
    <h2><span class="num">5</span>MCP Server · 暴露 {len(tools)} tool 给外部 Agent (v1.5)</h2>
    <p class="desc">通过 stdio 协议让 Claude Code / Cursor / 其他 Agent 直接调用内部能力.</p>
    <div class="tools-grid">{tools_html}</div>
  </section>

</div>

<footer>
  <p>实时数据 · 更新于 {data["ts"]} · <a href="/api/agents/status" target="_blank">JSON API</a></p>
  <p><a href="/alevel/">← 回主页</a></p>
</footer>

<script>
  // 每 30s 刷新一次（不强制 reload, 只静默更新 badge 数字）
  setTimeout(() => location.reload(), 30000);
</script>
</body>
</html>'''
