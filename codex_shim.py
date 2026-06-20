"""codex OAuth → OpenAI / Anthropic 兼容 HTTP API shim

把本地 codex CLI (ChatGPT OAuth) 包装成 HTTP API，让 A-Level Agent 通过
ANTHROPIC_BASE_URL=http://localhost:18891 或 OPENAI_BASE_URL 调到这里。

支持：
  ✅ 纯文本 chat completion
  ✅ Image input（codex CLI v0.115+ --image flag · PNG/JPEG/GIF/WebP）
  ✅ OpenAI image_url base64 / file URL / pure URL
  ✅ Anthropic image source (base64 / url)
  ❌ 流式（codex 输出是分段 JSON 事件，我们只取最后 agent_message）

⚠️ 性能：
  - codex exec 每次都 agentic loop → 6-30s 延迟（首次冷启慢，后续 cached）
  - 服务 ChatGPT Plus/Pro 包月（无 token 计费但有每小时 cap）
  - 仅供开发/演示，不适合 prod

支持的 endpoint：
  POST /v1/chat/completions         OpenAI 格式
  POST /v1/messages                 Anthropic 格式
  GET  /health                      健康检查

启动:
    python codex_shim.py
    # 或 PORT=18891 CODEX_SHIM_MODEL=gpt-5.5 python codex_shim.py
"""
from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import logging
import os
import re
import tempfile
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
_log = logging.getLogger("codex-shim")


CODEX_MODEL = os.environ.get("CODEX_SHIM_MODEL", "gpt-5.5")
CODEX_TIMEOUT = int(os.environ.get("CODEX_SHIM_TIMEOUT", "120"))

# codex --image 支持的格式（其他格式必须转）
SUPPORTED_IMAGE_MIME = {
    "image/png":  ".png",
    "image/jpeg": ".jpg",
    "image/jpg":  ".jpg",
    "image/gif":  ".gif",
    "image/webp": ".webp",
}


app = FastAPI(title="codex OAuth → OpenAI/Anthropic shim", version="0.1.0")


# ─────────────────────────────────────────────────────────────
# OpenAI types (subset)
# ─────────────────────────────────────────────────────────────
class OAIChatMessage(BaseModel):
    role: str
    content: str | list


class OAIChatRequest(BaseModel):
    model: str | None = None
    messages: list[OAIChatMessage]
    max_tokens: int | None = None
    temperature: float | None = None
    stream: bool | None = False


# ─────────────────────────────────────────────────────────────
# Anthropic types (subset)
# ─────────────────────────────────────────────────────────────
class AnthropicMessage(BaseModel):
    role: str
    content: str | list


class AnthropicRequest(BaseModel):
    model: str | None = None
    messages: list[AnthropicMessage]
    system: str | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    stream: bool | None = False


# ─────────────────────────────────────────────────────────────
# Core: messages → prompt → codex exec → completion text
# ─────────────────────────────────────────────────────────────
def _save_image_to_tmp(data_or_url: str, idx: int) -> str | None:
    """把 base64 / URL 转成临时文件路径返回。失败返回 None。

    支持的输入格式：
      - data:image/png;base64,XXXX           (OpenAI image_url 内联)
      - http(s)://...                         (远程 URL → 下载)
      - 纯文件路径                            (已落地，直接返回)
      - 纯 base64（无 prefix · 假设 png）
    """
    if not data_or_url:
        return None

    # 1. data: URI
    if data_or_url.startswith("data:"):
        m = re.match(r"data:(image/[a-zA-Z+]+);base64,(.+)", data_or_url, re.DOTALL)
        if not m:
            _log.warning("Unrecognized data URI; expected image/* base64")
            return None
        mime = m.group(1).lower()
        b64 = m.group(2)
        ext = SUPPORTED_IMAGE_MIME.get(mime, ".png")
        try:
            blob = base64.b64decode(b64)
        except Exception as e:
            _log.warning("base64 decode failed: %s", e)
            return None
        tmp = tempfile.NamedTemporaryFile(prefix=f"codex_shim_img_{idx}_", suffix=ext, delete=False)
        tmp.write(blob)
        tmp.close()
        return tmp.name

    # 2. http(s) URL
    if data_or_url.startswith(("http://", "https://")):
        try:
            with urllib.request.urlopen(data_or_url, timeout=30) as resp:
                blob = resp.read()
                ctype = resp.headers.get("Content-Type", "image/png").split(";")[0].strip()
                ext = SUPPORTED_IMAGE_MIME.get(ctype.lower(), ".png")
        except Exception as e:
            _log.warning("Failed to download image %s: %s", data_or_url, e)
            return None
        tmp = tempfile.NamedTemporaryFile(prefix=f"codex_shim_img_{idx}_", suffix=ext, delete=False)
        tmp.write(blob)
        tmp.close()
        return tmp.name

    # 3. 本地路径
    if os.path.exists(data_or_url):
        return data_or_url

    # 4. 纯 base64（无 data: prefix）— 容错处理
    try:
        blob = base64.b64decode(data_or_url)
        if len(blob) < 100:
            return None  # 太小，多半不是图
        tmp = tempfile.NamedTemporaryFile(prefix=f"codex_shim_img_{idx}_", suffix=".png", delete=False)
        tmp.write(blob)
        tmp.close()
        return tmp.name
    except Exception:
        return None


def _extract_text_and_images(content: str | list, idx_base: int = 0) -> tuple[str, list[str]]:
    """从 content (str 或 list-of-parts) 抽出 (纯文本, 图片临时文件路径列表)

    支持的 content 格式：
      OpenAI: [{"type": "text", "text": "..."}, {"type": "image_url", "image_url": {"url": "data:..."}}]
      Anthropic: [{"type": "text", "text": "..."}, {"type": "image", "source": {"type": "base64", "media_type": "...", "data": "..."}}]
    """
    if isinstance(content, str):
        return content, []

    if not isinstance(content, list):
        return str(content), []

    text_parts = []
    image_files = []

    for i, item in enumerate(content):
        if isinstance(item, str):
            text_parts.append(item)
            continue
        if not isinstance(item, dict):
            continue

        ctype = item.get("type", "")

        if ctype == "text":
            text_parts.append(item.get("text", ""))

        elif ctype == "image_url":
            # OpenAI 格式
            img_obj = item.get("image_url", {})
            url = img_obj.get("url") if isinstance(img_obj, dict) else img_obj
            if url:
                tmp_path = _save_image_to_tmp(url, idx_base + i)
                if tmp_path:
                    image_files.append(tmp_path)
                else:
                    text_parts.append("[image attachment failed to load]")

        elif ctype == "image":
            # Anthropic 格式
            src = item.get("source", {})
            src_type = src.get("type", "base64")
            if src_type == "base64":
                media = src.get("media_type", "image/png")
                data = src.get("data", "")
                if data:
                    data_uri = f"data:{media};base64,{data}"
                    tmp_path = _save_image_to_tmp(data_uri, idx_base + i)
                    if tmp_path:
                        image_files.append(tmp_path)
                    else:
                        text_parts.append("[image attachment failed to load]")
            elif src_type == "url":
                url = src.get("url", "")
                if url:
                    tmp_path = _save_image_to_tmp(url, idx_base + i)
                    if tmp_path:
                        image_files.append(tmp_path)

    return "\n".join(text_parts).strip(), image_files


def _build_prompt(messages: list, system: str | None = None) -> tuple[str, list[str]]:
    """把 messages 拼成单一 prompt + 图片列表 给 codex exec"""
    lines = []
    all_images: list[str] = []

    if system:
        lines.append(f"## System Instructions\n\n{system}\n")

    for i, msg in enumerate(messages):
        role = (msg.role if hasattr(msg, "role") else msg.get("role", "user")).lower()
        content = msg.content if hasattr(msg, "content") else msg.get("content", "")
        text, images = _extract_text_and_images(content, idx_base=i * 100)
        all_images.extend(images)

        if role == "system":
            lines.append(f"## System\n\n{text}\n")
        elif role == "assistant":
            lines.append(f"## Assistant (previous turn)\n\n{text}\n")
        else:
            if images:
                lines.append(f"## User\n\n[{len(images)} image(s) attached below]\n\n{text}\n")
            else:
                lines.append(f"## User\n\n{text}\n")

    # 最后一段提示 codex 直接回答（最小化 agentic loop）
    lines.append(
        "## Task\n\n"
        "Provide a direct response to the last user message above. "
        "Do NOT search the filesystem or run shell commands unless absolutely necessary. "
        "Do NOT load any external skills or memory files. "
        "Output ONLY the final answer text—no preamble, no meta-commentary."
    )
    return "\n".join(lines), all_images


# 并发上限 · 实测 2 路并行 codex CLI OK (codex 进程独立, ChatGPT 后端能接 ≥2 路).
# 设为 2 让 demo 里 Grader + Verifier 能并行, 把 5 agent 总时长从 ~65s 砍到 ~50s.
# 别再升 — 同账号同时 3+ 路 codex 会被 ChatGPT 端 throttle / 429.
_codex_sem = asyncio.Semaphore(2)


async def _call_codex(prompt: str, images: list[str] | None = None) -> tuple[str, dict]:
    """跑 codex exec --json [--image FILE ...]，解析最后的 agent_message
    所有调用走 _codex_sem 强制串行，避免 anthropic SDK retry 撞车。
    """
    async with _codex_sem:
        return await _call_codex_unlocked(prompt, images)


async def _call_codex_unlocked(prompt: str, images: list[str] | None = None) -> tuple[str, dict]:
    start = time.time()
    cmd = [
        "codex", "exec",
        "--skip-git-repo-check",
        "--json",
        "-c", "approval_policy=never",
        "-c", "sandbox_mode=read-only",
    ]
    image_files: list[str] = list(images or [])
    for img_path in image_files:
        cmd.extend(["--image", img_path])
    # 当有 --image (nargs=...) 时必须用 `--` 分隔 prompt，否则 prompt 被当成图片文件
    if image_files:
        cmd.append("--")
    cmd.append(prompt)

    _log.info(
        "Calling codex exec (timeout=%ds, images=%d)...",
        CODEX_TIMEOUT, len(image_files),
    )

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=CODEX_TIMEOUT,
        )
    except asyncio.TimeoutError:
        proc.kill()
        raise HTTPException(504, f"codex exec timeout after {CODEX_TIMEOUT}s")

    elapsed = time.time() - start
    if proc.returncode != 0:
        err = stderr.decode("utf-8", errors="replace")
        _log.error("codex exec failed (code=%d): %s", proc.returncode, err[:500])
        raise HTTPException(502, f"codex exec failed: {err[:300]}")

    raw = stdout.decode("utf-8", errors="replace")
    last_agent_msg = ""
    usage = {}

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        et = event.get("type", "")
        if et == "item.completed":
            item = event.get("item", {})
            if item.get("type") == "agent_message":
                last_agent_msg = item.get("text", "")
        elif et == "turn.completed":
            usage = event.get("usage", {})

    _log.info(
        "codex exec done in %.1fs (input=%s, cached=%s, output=%s)",
        elapsed,
        usage.get("input_tokens"),
        usage.get("cached_input_tokens"),
        usage.get("output_tokens"),
    )

    if not last_agent_msg:
        raise HTTPException(502, "codex exec returned no agent_message")

    # 清理图片临时文件
    for img_path in image_files:
        if img_path.startswith(tempfile.gettempdir()):
            with contextlib.suppress(OSError):
                os.unlink(img_path)

    return last_agent_msg, usage


# ─────────────────────────────────────────────────────────────
# OpenAI /v1/chat/completions
# ─────────────────────────────────────────────────────────────
@app.post("/v1/chat/completions")
async def openai_chat_completions(req: OAIChatRequest):
    if req.stream:
        raise HTTPException(400, "streaming not supported by codex shim")

    prompt, images = _build_prompt(req.messages)
    text, usage = await _call_codex(prompt, images=images)

    return JSONResponse({
        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": req.model or CODEX_MODEL,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": text},
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens":     usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
            "total_tokens": (
                usage.get("input_tokens", 0)
                + usage.get("output_tokens", 0)
            ),
        },
    })


# ─────────────────────────────────────────────────────────────
# Anthropic /v1/messages
# ─────────────────────────────────────────────────────────────
@app.post("/v1/messages")
async def anthropic_messages(req: AnthropicRequest):
    if req.stream:
        raise HTTPException(400, "streaming not supported by codex shim")

    prompt, images = _build_prompt(req.messages, system=req.system)
    text, usage = await _call_codex(prompt, images=images)

    return JSONResponse({
        "id": f"msg_{uuid.uuid4().hex[:24]}",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": text}],
        "model": req.model or CODEX_MODEL,
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {
            "input_tokens":  usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
        },
    })


# ─────────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    # 实际跑一个最小 codex 调用确认 OAuth 还有效
    try:
        text, _usage = await asyncio.wait_for(
            _call_codex("Respond with exactly: OK"),
            timeout=60,
        )
        return {"status": "ok", "codex_response": text[:50]}
    except Exception as e:
        return JSONResponse({"status": "fail", "error": str(e)}, status_code=503)


@app.get("/capabilities")
async def capabilities():
    """让 client 知道这个 shim 支持什么 - 给 A-Level project debug 用"""
    return {
        "model": CODEX_MODEL,
        "image_input": True,
        "supported_image_formats": list(SUPPORTED_IMAGE_MIME.keys()),
        "streaming": False,
        "max_timeout_seconds": CODEX_TIMEOUT,
    }


@app.get("/")
async def root():
    return {
        "service": "codex-shim",
        "version": "0.1.0",
        "model": CODEX_MODEL,
        "endpoints": {
            "openai": "POST /v1/chat/completions",
            "anthropic": "POST /v1/messages",
            "health": "GET /health",
        },
        "warning": (
            "Each call shells out to `codex exec` (≥30s latency, "
            "ChatGPT Plus/Pro quota consumed). NOT for production."
        ),
    }


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 18891))
    _log.info("Starting codex-shim on :%d (CODEX_TIMEOUT=%ds)", port, CODEX_TIMEOUT)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
