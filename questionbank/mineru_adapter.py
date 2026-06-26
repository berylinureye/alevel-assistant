"""Thin wrapper around the MinerU CLI for question-bank PDF parsing."""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = Path("data/mineru_output")
DEFAULT_BACKEND = "pipeline"
DEFAULT_METHOD = "auto"
DEFAULT_LANG = "ch"
DEFAULT_TIMEOUT_SECONDS = 1200


class MinerUError(RuntimeError):
    """Base class for MinerU adapter errors."""


class MinerUNotAvailableError(MinerUError):
    """Raised when the MinerU CLI cannot be found."""


class MinerUExecutionError(MinerUError):
    """Raised when the MinerU CLI exits unsuccessfully."""


@dataclass
class MinerUResult:
    input_path: Path
    output_dir: Path
    markdown_path: Optional[Path] = None
    content_list_path: Optional[Path] = None
    content_list_v2_path: Optional[Path] = None
    middle_json_path: Optional[Path] = None
    model_json_path: Optional[Path] = None
    stdout: str = ""
    stderr: str = ""


def _as_project_path(value: str | Path, project_root: Path = PROJECT_ROOT) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return project_root / path


def find_mineru_executable(project_root: Path = PROJECT_ROOT) -> Path:
    """Return the configured MinerU executable or raise a clear setup error."""
    configured = os.environ.get("MINERU_BIN", "").strip()
    candidates: list[Path] = []
    if configured:
        candidates.append(_as_project_path(configured, project_root))
    candidates.append(project_root / ".venv-mineru" / "bin" / "mineru")

    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate

    path_hit = shutil.which("mineru")
    if path_hit:
        return Path(path_hit)

    hint = (
        "MinerU CLI not found. Set MINERU_BIN or install the isolated runtime with "
        "`uv venv --python <python3.10+> .venv-mineru && "
        "uv pip install --python .venv-mineru/bin/python -U \"mineru[all]\"`."
    )
    if configured:
        hint = f"MINERU_BIN points to {configured!r}, but it is not executable. " + hint
    raise MinerUNotAvailableError(hint)


def mineru_available(project_root: Path = PROJECT_ROOT) -> bool:
    try:
        find_mineru_executable(project_root=project_root)
    except MinerUNotAvailableError:
        return False
    return True


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _should_force_arm64() -> bool:
    configured = os.environ.get("MINERU_FORCE_ARM64")
    if configured is not None:
        return _truthy(configured)
    if sys.platform != "darwin" or platform.machine() != "x86_64":
        return False
    if not Path("/usr/bin/arch").exists():
        return False
    try:
        completed = subprocess.run(
            ["/usr/sbin/sysctl", "-in", "hw.optional.arm64"],
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return False
    return completed.stdout.strip() == "1"


def _mineru_command(mineru_bin: Path) -> list[str]:
    if _should_force_arm64():
        return ["/usr/bin/arch", "-arm64", str(mineru_bin)]
    return [str(mineru_bin)]


def run_mineru_parse(
    pdf_path: str | Path,
    *,
    output_dir: str | Path | None = None,
    backend: str | None = None,
    method: str | None = None,
    lang: str | None = None,
    timeout_seconds: int | None = None,
    start_page: int | None = None,
    end_page: int | None = None,
) -> MinerUResult:
    """Parse a PDF with MinerU and return discovered output files."""
    input_path = Path(pdf_path).expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(input_path)

    resolved_output = _as_project_path(
        output_dir or os.environ.get("MINERU_OUTPUT_DIR", DEFAULT_OUTPUT_DIR)
    )
    resolved_output.mkdir(parents=True, exist_ok=True)

    mineru_bin = find_mineru_executable()
    resolved_backend = backend or os.environ.get("MINERU_BACKEND", DEFAULT_BACKEND)
    resolved_method = method or os.environ.get("MINERU_METHOD", DEFAULT_METHOD)
    resolved_lang = lang or os.environ.get("MINERU_LANG", DEFAULT_LANG)
    resolved_timeout = int(
        timeout_seconds or os.environ.get("MINERU_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)
    )

    cmd = [
        *_mineru_command(mineru_bin),
        "-p",
        str(input_path),
        "-o",
        str(resolved_output),
        "-b",
        resolved_backend,
        "-m",
        resolved_method,
        "-l",
        resolved_lang,
    ]
    api_url = os.environ.get("MINERU_API_URL", "").strip()
    if api_url:
        cmd.extend(["--api-url", api_url])
    if start_page is not None:
        cmd.extend(["-s", str(start_page)])
    if end_page is not None:
        cmd.extend(["-e", str(end_page)])

    try:
        completed = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            text=True,
            capture_output=True,
            timeout=resolved_timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise MinerUExecutionError(
            f"MinerU parse timed out after {resolved_timeout} seconds for {input_path}."
        ) from exc
    if completed.returncode != 0:
        raise MinerUExecutionError(
            "MinerU parse failed with exit code "
            f"{completed.returncode}.\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )

    result = _discover_outputs(input_path, resolved_output)
    result.stdout = completed.stdout
    result.stderr = completed.stderr
    return result


def _discover_outputs(input_path: Path, output_dir: Path) -> MinerUResult:
    stem = input_path.stem

    def first_match(patterns: list[str]) -> Optional[Path]:
        matches: list[Path] = []
        for pattern in patterns:
            matches.extend(output_dir.rglob(pattern))
        matches = sorted(
            {p for p in matches if p.is_file()},
            key=lambda p: (0 if stem in p.stem else 1, len(p.parts), str(p)),
        )
        return matches[0] if matches else None

    return MinerUResult(
        input_path=input_path,
        output_dir=output_dir,
        markdown_path=first_match([f"{stem}.md", f"{stem}_*.md", "*.md"]),
        content_list_path=first_match(
            [f"{stem}_content_list.json", "*_content_list.json"]
        ),
        content_list_v2_path=first_match(
            [f"{stem}_content_list_v2.json", "*_content_list_v2.json"]
        ),
        middle_json_path=first_match([f"{stem}_middle.json", "*_middle.json"]),
        model_json_path=first_match([f"{stem}_model.json", "*_model.json"]),
    )


def read_mineru_text(result: MinerUResult) -> str:
    """Read text from MinerU outputs, preferring structured content lists."""
    for path in (result.content_list_path, result.content_list_v2_path):
        if path and path.exists():
            text = _read_content_list_text(path)
            if text.strip():
                return text

    if result.markdown_path and result.markdown_path.exists():
        return result.markdown_path.read_text(encoding="utf-8").strip()

    return ""


def _read_content_list_text(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    parts = list(_iter_content_text(data))
    return "\n\n".join(part.strip() for part in parts if part and part.strip())


def _iter_content_text(value: Any):
    if isinstance(value, list):
        for item in value:
            yield from _iter_content_text(item)
        return

    if not isinstance(value, dict):
        return

    for key in (
        "text",
        "table_body",
        "code_body",
        "paragraph_content",
        "math_content",
        "title_content",
        "content",
    ):
        if key not in value:
            continue
        nested = value[key]
        if isinstance(nested, str):
            yield nested
        else:
            yield from _iter_content_text(nested)

    for list_key in ("image_caption", "table_caption", "chart_caption", "list_items"):
        nested_list = value.get(list_key)
        if isinstance(nested_list, list):
            yield from _iter_content_text(nested_list)
