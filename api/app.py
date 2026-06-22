"""
FastAPI 应用实例。
lifespan 负责加载环境变量；全局异常处理器兜底未捕获异常。
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os

# Ensure INFO-level logs from our modules (grader / verifier / segmenter / pipeline)
# surface in uvicorn's stdout. uvicorn installs its own handlers for its own loggers;
# root handler here catches everything else. Safe to call multiple times (force=True).
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
    force=True,
)
for _noisy in ("httpx", "httpcore", "urllib3", "watchfiles"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

from fastapi.staticfiles import StaticFiles
from pathlib import Path

from api.routes import router
from api.qb_routes import qb_router
from api.feedback import feedback_router
from api.practice_orchestrator import practice_orchestrator_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_dotenv(override=True)
    from router.models import build_registry
    app.state.registry = build_registry()
    yield


app = FastAPI(
    title       = "A-Level 作业助手 API",
    version     = "0.1.0",
    description = "Upload a homework page image and receive structured grading results.",
    lifespan    = lifespan,
)

# CORS — 允许前端跨域访问后端 API
# 生产环境通过 ALLOWED_ORIGINS 环境变量限制来源，逗号分隔
_raw_origins = os.environ.get("ALLOWED_ORIGINS", "")
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()] if _raw_origins else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(qb_router)
app.include_router(practice_orchestrator_router)
app.include_router(feedback_router)

# /showcase · 面试官 demo 落地页 (主路径)
try:
    from api.showcase import showcase_router
    app.include_router(showcase_router)
except Exception as _e:
    logging.getLogger("api.app").warning(f"showcase not loaded: {_e}")

# /pitch · 产品负责人视角的产品介绍页
try:
    from api.pitch import pitch_router
    app.include_router(pitch_router)
except Exception as _e:
    logging.getLogger("api.app").warning(f"pitch not loaded: {_e}")

# /api/showcase/demo-grade · showcase 页交互式 demo · 真实调 codex
try:
    from api.demo_grade import demo_router
    app.include_router(demo_router)
except Exception as _e:
    logging.getLogger("api.app").warning(f"demo_grade not loaded: {_e}")

# /agents · 技术 deep-dive 页 + /agent-banner.js (默认隐藏, 通过 showcase 折叠区进入)
try:
    from api.agents_inspector import agents_router
    app.include_router(agents_router)
except Exception as _e:
    logging.getLogger("api.app").warning(f"agents_inspector not loaded: {_e}")


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # 避免把内部异常细节直接暴露给前端（生产环境仅返回通用信息）
    debug = os.environ.get("DEBUG", "").lower() in {"1", "true", "yes", "on"}
    return JSONResponse(
        status_code=500,
        content={
            "status":     "error",
            "error_code": "INTERNAL_ERROR",
            "message":    (str(exc) if debug else "Internal server error."),
        },
    )


@app.get("/health", include_in_schema=False)
async def health() -> dict:
    return {"status": "ok"}


_frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"


@app.get("/__debug_fs", include_in_schema=False)
async def debug_fs() -> dict:
    import os
    base = _frontend_dist.parent.parent
    return {
        "dist_path": str(_frontend_dist),
        "dist_exists": _frontend_dist.is_dir(),
        "root_listing": sorted(os.listdir(str(base))) if base.is_dir() else "missing",
        "frontend_listing": sorted(os.listdir(str(base / "frontend"))) if (base / "frontend").is_dir() else "missing",
    }


@app.get("/__debug_keys", include_in_schema=False)
async def debug_keys() -> dict:
    import os
    def describe(name: str) -> dict:
        v = os.environ.get(name, "")
        return {
            "set": bool(v),
            "length": len(v),
            "stripped_length": len(v.strip()),
            "prefix": v[:8] if v else "",
            "has_whitespace": v != v.strip(),
        }
    return {
        "DASHSCOPE_API_KEY": describe("DASHSCOPE_API_KEY"),
        "DEEPSEEK_API_KEY": describe("DEEPSEEK_API_KEY"),
        "GLM_API_KEY": describe("GLM_API_KEY"),
        "ANTHROPIC_API_KEY": describe("ANTHROPIC_API_KEY"),
    }


from fastapi.responses import FileResponse
from starlette.types import Scope


# Cache headers for SPA assets:
# - index.html (and any other non-hashed HTML fallback): must NOT be cached by browsers,
#   otherwise post-deploy users keep requesting hashed asset names that no longer exist.
# - /assets/* : filenames are content-hashed by Vite, so safe to cache aggressively.
_INDEX_CACHE_HEADERS = {"Cache-Control": "no-cache, must-revalidate"}
_ASSET_CACHE_HEADERS = {"Cache-Control": "public, max-age=31536000, immutable"}


class _ImmutableAssets(StaticFiles):
    """StaticFiles subclass that stamps `Cache-Control: immutable` on every hit.

    Vite emits content-hashed filenames under /assets/*, so these bytes are by
    definition immutable for their URL — a new build produces new filenames.
    """

    async def get_response(self, path: str, scope: Scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            for k, v in _ASSET_CACHE_HEADERS.items():
                response.headers[k] = v
        return response


# /static/ → showcase demo 用的 fixture 图片
_static_dir = Path(__file__).resolve().parent.parent / "static"
if _static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

if _frontend_dist.is_dir():
    app.mount("/assets", _ImmutableAssets(directory=str(_frontend_dist / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        candidate = _frontend_dist / full_path
        if full_path and candidate.is_file():
            # Non-hashed top-level files (favicon.svg, icons.svg, landing/*, etc.)
            # should revalidate on each load to avoid stale references.
            return FileResponse(str(candidate), headers=_INDEX_CACHE_HEADERS)
        return FileResponse(str(_frontend_dist / "index.html"), headers=_INDEX_CACHE_HEADERS)
