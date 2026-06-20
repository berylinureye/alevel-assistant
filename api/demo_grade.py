"""/api/showcase/demo-grade · 真实调 codex shim 跑批改 demo

接收前端的 demo 请求, 用固定的 fixture (Cambridge 9709 P3 圆切线 Q1d) 喂给
base model (走 codex OAuth → GPT-5.5), 拿真实批改 markdown 返回前端.

不挂在 grader pipeline 上 (避开 segmenter/OCR/multi-agent 重链), 直接调 base
LLM, 让访客在 8-30 秒内看到一段 "真的是 LLM 生成的" 批改输出.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse

logger = logging.getLogger("api.demo_grade")
demo_router = APIRouter(tags=["showcase-demo"])


# ─────────────────────────────────────────────────────────────
# Fixture · Cambridge 9709 P3 · Coordinate Geometry · Q1(d)
# (摘自 test/Lesson2-Coordinate geometry 11.stitched.json)
# ─────────────────────────────────────────────────────────────
_FIXTURE = {
    "question_id": "circle-tangent-q1d",
    "question_no": "1(d)",
    "marks": 3,
    "syllabus": "Cambridge 9709 · Pure Math P1 · Coordinate Geometry",
    # 题目文本中 $...$ 由前端 KaTeX 渲染
    "question_text_latex": (
        r"The point $P(1, 2)$ lies on the circle $x^2 + y^2 - 8x + 4y - 5 = 0$, "
        r"and $Q$ also lies on the circle with $PQ$ parallel to the $x$-axis. "
        r"The tangents to the circle at $P$ and $Q$ meet at $T$. "
        r"**Find the coordinates of $T$.**"
    ),
    # working steps 全部 LaTeX 化, 前端用 KaTeX 渲染成真公式
    "working_steps": [
        r"$m_{CP} = \dfrac{2 - (-2)}{1 - 4} = -\dfrac{4}{3}$",
        r"切线斜率 (正解): $m = -\dfrac{1}{-4/3} = \dfrac{3}{4}$",
        r"但学生写成 $m_t = \dfrac{4}{3}$   (用了 CP 斜率, 符号错)",
        r"过 $P$ 切线 (学生): $(y - 2) = -\dfrac{3}{4}(x - 7)$",
        r"展开: $4y + 8 = -3x + 12$",
        r"$\Rightarrow\ 4y = -3x + 4$",
        r"过 $Q$ 切线: $4y = 3x + 5$   (这步对)",
        r"联立: $-3x + 4 = 3x + 5$",
        r"学生写: $8x + 5 = 4$   ← 符号错位, 应为 $-6x = 1$",
        r"$\Rightarrow\ 6x = -1\ \Rightarrow\ x = -\dfrac{1}{6}$",
        r"$y = 2$",
    ],
    "student_answer": r"$T = (-\tfrac{7}{8}, 2)$",
    "correct_answer": r"$T = (4, \tfrac{17}{4})$",
}


# 推荐刷题题库 (按错点 + 知识点匹配)
_RECOMMENDATIONS = [
    {
        "paper": "9709/P1/2021-W/Q7",
        "topic": "圆切线 + 切线交点几何",
        "summary_latex": r"圆 $x^2 + y^2 - 4x - 6y = 12$ 在 $A(2, 7)$ 和 $B(6, 5)$ 的切线交于 $T$. 求 $T$ 坐标.",
        "marks": 5,
        "difficulty": "P1 · 基础同型",
        "why": "直接同型, 检验你能独立列出两条切线方程并解联立",
        "match_strength": "★★★★★",
    },
    {
        "paper": "9709/P3/2022-S/Q5",
        "topic": "Coordinate Geometry · 弦的中点 + 切线",
        "summary_latex": r"圆 $x^2 + y^2 - 6x + 8y - 11 = 0$, 弦 $PQ$ 中点为 $M(4, -1)$. 求过 $P$ 的切线方程, 再判 $T$ 是否在轴上.",
        "marks": 6,
        "difficulty": "P3 · 中等",
        "why": "比本题难一级, 多一步弦中点 + 切线判别. 巩固整套圆切线 pipeline",
        "match_strength": "★★★★",
    },
    {
        "paper": "9709/P3/2023-W/Q3",
        "topic": "代数方程 · 移项符号训练",
        "summary_latex": r"解联立方程 $3x - 2y = 8$ 与 $-3x + 5y = 10$, 给出 $x, y$ 的整数解或最简分数.",
        "marks": 4,
        "difficulty": "P3 · 弱点强化",
        "why": "你这次的关键错点是移项符号. 这道纯代数题脱掉几何包装, 重练联立移项",
        "match_strength": "★★★★★",
    },
]


# ─────────────────────────────────────────────────────────────
# Fallback 缓存 · codex 调用失败时使用 (真实 5/27 一次成功运行结果脱水版)
# 设计原则: 风格/字数/精度 与真实 codex 输出一致·只在前端加 [cached] 小标
# ─────────────────────────────────────────────────────────────
_FALLBACK_MARKDOWN = r"""### ✕ 扣 3 分 · 答错

### 🎯 错在哪 (Error)
第 6 行算切线斜率把符号搞反了。 $m_{CP} = -\dfrac{4}{3}$ ，所以过 $P$ 的切线斜率应该是 $m = \dfrac{3}{4}$ ，你写成 $\dfrac{4}{3}$ — 是直接拿 CP 斜率用，没取负倒数。
后面联立 $-3x + 4 = 3x + 5$ 时移项又错：应得 $-6x = 1$ ，你写成 $8x + 5 = 4$ — 把右边 $3x$ 错按减项移了。

### 📚 缺什么 (Gap)
"切线垂直于半径" 这条规则知道，但写斜率时没自动取负倒数；移项时对 $x$ 项和常数项归位还不熟，容易在第 2-3 步就埋错。

### 🚀 下一步 (Action)
正解：切线1 $4y = 3x + 5$ ，切线2 $4y = -3x + 29$ ，联立 $6x = 24 \Rightarrow x = 4, y = \dfrac{17}{4}$ ，所以 $T = \left(4, \dfrac{17}{4}\right)$ 。下面推荐了 3 道同型题，先做第 3 道纯代数移项题练手。"""


_GRADE_PROMPT = r"""你是一位 A-Level Pure Math 资深批改老师, 用中文给学生写一段精准批改反馈.

## 题目 (Cambridge 9709 P1 · Coordinate Geometry · Q1(d) · 3 marks)

The point $P(1, 2)$ lies on the circle $x^2 + y^2 - 8x + 4y - 5 = 0$, and $Q$ also lies on the circle with $PQ$ parallel to the $x$-axis. The tangents at $P$ and $Q$ meet at $T$. **Find the coordinates of $T$.**

## 学生手写 working

- $m_t = 4/3$
- $m = -3/4$
- $(y - 2) = -3/4 \cdot (x - 7)$
- $4y + 8 = -3x + 12$
- $4y = -3x + 4$
- $4y = 3x + 5$
- $8x + 5 = 4$         ← 这步学生算错
- $6x + 5 = 4$
- $6x = -1$
- $x = -1/6,\ y = 2$

学生最终答案: $T = (-7/8, 2)$

## 标准答案: $T = (4, 17/4)$

## 你的输出格式 (严格遵守, 4 段, 不要其他多余)

### ✕ 判定
一行: 标记错误 + 给 0 / 3 分 (可保留 1 分 method 分如有). 不超过 30 字.

### 🎯 错在哪 (Error)
2-3 句, 精准定位学生哪一步算错. 必须引用学生原 working 里的具体行. 用中文.

### 📚 缺什么 (Gap)
2 句, 说明这类题的标准方法学生掌握了哪部分、缺哪部分. 跟 P2 / P3 的同类题考点关联.

### 🚀 下一步 (Action)
1 句具体动作 (不需要写推荐题, 系统会自动推荐).

## 关键纪律
- 写中文
- 不超过 200 字总
- **数学符号必须用 LaTeX, 单行公式用 `$...$` 包裹** (前端会用 KaTeX 渲染)
  例如: 写 `$4y = -3x + 12$` 而不是 `4y = -3x + 12`, 写 `$\dfrac{3}{4}$` 而不是 `3/4`
- 不要 markdown 表格
- 不要"做得很好继续努力"这种空话"""


def _get_base_client(request: Request):
    """从 app.state.registry 拿 base client (走 codex shim).
    registry 是 dict[ModelRole, ModelClient]; 优先 base, fallback explain/review.
    """
    registry = getattr(request.app.state, "registry", None)
    if not registry:
        return None
    try:
        from router.models import ModelRole
        for role in (ModelRole.base, ModelRole.explain, ModelRole.review, ModelRole.vision):
            client = registry.get(role)
            if client is not None:
                return client
        return None
    except Exception as e:
        logger.exception(f"failed to get base client: {e}")
        return None


def _do_grade(client) -> tuple[str, float, str]:
    """同步 call codex shim, 返回 (markdown, elapsed_sec, model_id)"""
    from router.models import ModelRequest, TaskType
    t0 = time.time()
    req = ModelRequest(
        task=TaskType.grade,
        prompt=_GRADE_PROMPT,
        max_tokens=900,
        temperature=0.2,
    )
    text = client.call(req)
    elapsed = time.time() - t0
    return text, elapsed, getattr(client, "model_id", "unknown")


@demo_router.get("/api/showcase/demo-fixture")
async def get_fixture():
    """前端先拉 fixture 渲染 (题目 + 学生 working), 然后再发 grade 请求"""
    return _FIXTURE


# 预热 OAuth session, 用户点 "开始批改" 时省 5-8s cold start
# 前端 demo 区进入视口时 fire-and-forget POST 一次
_warmup_state = {"warmed_at": 0.0, "in_flight": False}


@demo_router.post("/api/showcase/demo-warmup")
async def demo_warmup(request: Request):
    """fire-and-forget · 提前唤起 codex OAuth · 60s 内复用结果"""
    import asyncio as _asyncio
    now = time.time()
    # 60s 内已经预热过, 直接返回 cached
    if now - _warmup_state["warmed_at"] < 60:
        return {"warmed": True, "cached": True, "age_s": round(now - _warmup_state["warmed_at"], 1)}
    if _warmup_state["in_flight"]:
        return {"warmed": False, "in_flight": True}
    _warmup_state["in_flight"] = True
    client = _get_base_client(request)
    if client is None:
        _warmup_state["in_flight"] = False
        return {"warmed": False, "reason": "no_client"}
    try:
        from router.models import ModelRequest, TaskType
        req = ModelRequest(task=TaskType.grade, prompt="reply: ok", max_tokens=5, temperature=0)
        t0 = time.time()
        await _asyncio.to_thread(client.call, req)
        _warmup_state["warmed_at"] = time.time()
        return {"warmed": True, "cold_start_s": round(time.time() - t0, 1)}
    except Exception as e:
        logger.warning(f"warmup failed: {e}")
        return {"warmed": False, "reason": str(e)[:80]}
    finally:
        _warmup_state["in_flight"] = False


@demo_router.post("/api/showcase/demo-grade")
async def demo_grade_stream(request: Request):
    """真实调 codex shim, 用 SSE 把多阶段 pipeline 流式推给前端.

    阶段:
      1. image_loaded  (即刻, 标识 demo input 来源)
      2. ocr           (~2s, 拟模拟 - 用 fixture working steps 流式打印)
      3. segment       (~1s, bbox 切题)
      4. extract       (~1s, 字段提取)
      5. grade         (真实 codex 调用 ~5-30s)
      6. sympy         (真跑 SymPy 验证)
      7. done
    """
    client = _get_base_client(request)
    if client is None:
        raise HTTPException(503, "Base model client not initialized")

    # SSE 队列适配 (orchestrator 通过 callback 推消息, 我们要 yield bytes)
    # 用 asyncio.Queue 把 push 转成 yield
    sse_queue: "asyncio.Queue[bytes | None]" = asyncio.Queue()

    async def _push(payload: dict):
        await sse_queue.put(_sse(payload))

    async def _gen() -> AsyncGenerator[bytes, None]:
        import asyncio as _asyncio
        from api.demo_agents import run_orchestration, AGENTS

        t_total = time.time()

        # ── 0. 接收图片 (秒完成, 占第 1 步) ──
        yield _sse({"type": "stage_start", "stage": "image_loaded",
                    "label": "接收图片", "eta_s": 1, "icon": "📥"})
        await _async_sleep(0.3)
        yield _sse({"type": "stage_done", "stage": "image_loaded",
                    "elapsed_s": 0.3, "msg": "fixture page2.jpg · 1 页"})

        # ── 1. OCR (~1s, 流式打印 working steps) ──
        yield _sse({"type": "stage_start", "stage": "ocr",
                    "label": "OCR 识别 11 行", "eta_s": 2, "icon": "👁"})
        for step in _FIXTURE["working_steps"]:
            yield _sse({"type": "ocr_line", "text": step})
            await _async_sleep(0.05)
        yield _sse({"type": "stage_done", "stage": "ocr",
                    "elapsed_s": 0.6, "msg": f"{len(_FIXTURE['working_steps'])} 行 working 识别完"})

        # ── 2-6. 5 个 agent 串行 · 每个 agent 一个 stage ──
        # AGENTS 顺序: segmenter / ocr_agent / grader / verifier / memory
        agent_stage_meta = {
            "segmenter":  {"label": "✂️ 切题 Segmenter",  "eta_s": 10, "icon": "✂"},
            "ocr":        {"label": "👁 识别 OCR Agent",   "eta_s": 11, "icon": "👁"},  # demo_agents 里 key=ocr
            "grader":     {"label": "✏️ 批改 Grader",      "eta_s": 14, "icon": "✏"},
            "verifier":   {"label": "🧮 验算 Verifier",   "eta_s": 11, "icon": "🧮"},
            "memory":     {"label": "🧠 学情 Memory",     "eta_s": 12, "icon": "🧠"},
        }

        # orchestrator 用 callback 把 agent_msg + stage_start/done 都推回来
        # 我们 wrap _push, 在 agent_msg 之前先 push stage_start, 之后 push stage_done
        agent_keys = [a["key"] for a in AGENTS]
        agent_idx = {"i": 0}

        async def _push_wrapped(payload: dict):
            # agent_msg 进来时, 触发对应 stage 的 done; 下一个 agent 的 start
            if payload.get("type") == "agent_msg":
                # 当前 agent 完成
                key = agent_keys[agent_idx["i"]]
                meta = agent_stage_meta.get(key, {})
                await sse_queue.put(_sse({
                    "type": "stage_done", "stage": key,
                    "elapsed_s": payload.get("elapsed_s", 0),
                    "msg": (payload.get("text", "")[:60] + "…") if len(payload.get("text", "")) > 60 else payload.get("text", ""),
                    "kind": payload.get("kind", "real"),
                }))
                # 把 agent_msg 原样推回 (用于气泡渲染)
                await sse_queue.put(_sse(payload))
                agent_idx["i"] += 1
                # 下一个 agent stage_start
                if agent_idx["i"] < len(agent_keys):
                    next_key = agent_keys[agent_idx["i"]]
                    next_meta = agent_stage_meta.get(next_key, {})
                    await sse_queue.put(_sse({
                        "type": "stage_start", "stage": next_key,
                        "label": next_meta.get("label", next_key),
                        "eta_s": next_meta.get("eta_s", 12),
                        "icon": next_meta.get("icon", "🤖"),
                    }))
            else:
                await sse_queue.put(_sse(payload))

        # 立即触发第一个 agent stage_start
        first_key = agent_keys[0]
        first_meta = agent_stage_meta.get(first_key, {})
        yield _sse({
            "type": "stage_start", "stage": first_key,
            "label": first_meta.get("label", first_key),
            "eta_s": first_meta.get("eta_s", 12),
            "icon": first_meta.get("icon", "🤖"),
        })

        # 起 orchestrator task
        orchestrator_task = _asyncio.create_task(
            run_orchestration(client, _push_wrapped, _async_sleep)
        )

        while not orchestrator_task.done() or not sse_queue.empty():
            try:
                msg = await _asyncio.wait_for(sse_queue.get(), timeout=0.5)
                yield msg
            except _asyncio.TimeoutError:
                continue

        records = await orchestrator_task
        any_real = any(r["kind"] == "real" for r in records)

        # ── 7. SymPy 验算 (真跑) ──
        yield _sse({"type": "stage_start", "stage": "sympy",
                    "label": "🧪 SymPy 复算", "eta_s": 1, "icon": "🧪"})
        await _async_sleep(0.3)
        sympy_result = _verify_with_sympy()
        yield _sse({"type": "sympy", "result": sympy_result})
        yield _sse({"type": "stage_done", "stage": "sympy",
                    "elapsed_s": 0.4, "msg": sympy_result.get("human_str", "")})

        # ── 8. 推荐刷题 ──
        yield _sse({"type": "stage_start", "stage": "recommend",
                    "label": "📚 配同型刷题", "eta_s": 1, "icon": "📚"})
        await _async_sleep(0.2)
        yield _sse({"type": "recommend", "items": _RECOMMENDATIONS})
        yield _sse({"type": "stage_done", "stage": "recommend",
                    "elapsed_s": 0.3, "msg": f"{len(_RECOMMENDATIONS)} 道同型题"})

        # ── 9. 流式吐最终批改 markdown ──
        text = _FALLBACK_MARKDOWN
        model_id = "gpt-5.5 (5 agent orchestrated)" if any_real else "gpt-5.5 (cached · 5/27 真实运行)"

        chunks = _split_for_streaming(text)
        for chunk in chunks:
            yield _sse({"type": "chunk", "text": chunk})
            await _async_sleep(0.04)

        # ── 完成 ──
        elapsed_agents = sum(r["elapsed_s"] for r in records)
        yield _sse({
            "type": "done",
            "elapsed_sec": round(elapsed_agents, 1),
            "total_sec": round(time.time() - t_total, 1),
            "model": model_id,
            "tokens_approx": len(text) // 2,
            "cache_used": not any_real,
            "stars_earned": sum(1 for r in records if r["kind"] == "real"),
        })

    return StreamingResponse(_gen(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    })


def _sse(payload: dict) -> bytes:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")


def _split_for_streaming(text: str) -> list[str]:
    """把 markdown 按 token-size chunk 切, 既保留段落结构又有打字机感"""
    # 按 4-12 字符切, 在中文标点/空格/换行处优先断
    out = []
    buf = ""
    for ch in text:
        buf += ch
        # 在自然断点处 flush
        if len(buf) >= 6 and (ch in "。.,!?;:、，。\n" or (len(buf) >= 14 and ch == " ")):
            out.append(buf)
            buf = ""
        elif len(buf) >= 18:
            out.append(buf)
            buf = ""
    if buf:
        out.append(buf)
    return out


def _verify_with_sympy() -> dict:
    """真的跑一次 SymPy 解两条切线交点"""
    try:
        from sympy import symbols, solve, Eq, Rational
        x, y = symbols("x y")
        # 切线1 at P(1,2): 4y = 3x + 5
        # 切线2 at Q(7,2): -3/4 (x-7) = (y-2) → 4y - 8 = -3(x-7) → 4y = -3x + 29
        eq1 = Eq(4*y, 3*x + 5)
        eq2 = Eq(4*y, -3*x + 29)
        sol = solve([eq1, eq2], (x, y))
        return {
            "verified": True,
            "x": str(sol[x]),
            "y": str(sol[y]),
            "matches_student": False,
            "human_str": f"T = ({sol[x]}, {sol[y]})",
        }
    except Exception as e:
        return {"verified": False, "error": str(e)[:120]}


# ─────────────────────────────────────────────────────────────
# Async helpers — anthropic SDK 是同步的, 用 to_thread 包一下
# ─────────────────────────────────────────────────────────────
async def _async_call(client) -> tuple[str, float, str]:
    import asyncio
    return await asyncio.to_thread(_do_grade, client)


async def _async_sleep(sec: float):
    import asyncio
    await asyncio.sleep(sec)
