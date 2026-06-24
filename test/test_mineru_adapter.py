from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from questionbank.mineru_adapter import (
    MinerUNotAvailableError,
    find_mineru_executable,
    read_mineru_text,
    run_mineru_parse,
    MinerUExecutionError,
)


def test_find_mineru_executable_prefers_env_path(tmp_path, monkeypatch):
    mineru_bin = tmp_path / "mineru"
    mineru_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    mineru_bin.chmod(0o755)

    monkeypatch.setenv("MINERU_BIN", str(mineru_bin))

    assert find_mineru_executable() == mineru_bin


def test_find_mineru_executable_raises_clear_error(monkeypatch):
    monkeypatch.setenv("MINERU_BIN", "/missing/mineru")
    monkeypatch.setenv("PATH", "")

    with pytest.raises(MinerUNotAvailableError) as exc:
        find_mineru_executable(project_root=Path("/tmp/no-such-project"))

    assert "MINERU_BIN" in str(exc.value)


def test_run_mineru_parse_invokes_cli_and_discovers_outputs(tmp_path, monkeypatch):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    output_dir = tmp_path / "mineru-output"
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append([str(part) for part in cmd])
        doc_dir = output_dir / "paper" / "auto"
        doc_dir.mkdir(parents=True)
        (doc_dir / "paper.md").write_text("# Paper\n\n1 Find x.", encoding="utf-8")
        (doc_dir / "paper_content_list.json").write_text(
            json.dumps([{"type": "text", "text": "1 Find x.", "page_idx": 0}]),
            encoding="utf-8",
        )

        class Completed:
            returncode = 0
            stdout = "ok"
            stderr = ""

        return Completed()

    mineru_bin = tmp_path / "mineru"
    mineru_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    mineru_bin.chmod(0o755)
    monkeypatch.setenv("MINERU_BIN", str(mineru_bin))
    monkeypatch.setenv("MINERU_FORCE_ARM64", "0")
    monkeypatch.setattr("questionbank.mineru_adapter.subprocess.run", fake_run)

    result = run_mineru_parse(
        pdf_path,
        output_dir=output_dir,
        backend="pipeline",
        method="auto",
        lang="ch",
        timeout_seconds=30,
    )

    assert calls == [
        [
            str(mineru_bin),
            "-p",
            str(pdf_path),
            "-o",
            str(output_dir),
            "-b",
            "pipeline",
            "-m",
            "auto",
            "-l",
            "ch",
        ]
    ]
    assert result.markdown_path == output_dir / "paper" / "auto" / "paper.md"
    assert result.content_list_path == output_dir / "paper" / "auto" / "paper_content_list.json"
    assert result.stdout == "ok"


def test_run_mineru_parse_can_force_arm64_launcher(tmp_path, monkeypatch):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    output_dir = tmp_path / "mineru-output"
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append([str(part) for part in cmd])
        (output_dir / "paper").mkdir(parents=True)

        class Completed:
            returncode = 0
            stdout = "ok"
            stderr = ""

        return Completed()

    mineru_bin = tmp_path / "mineru"
    mineru_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    mineru_bin.chmod(0o755)
    monkeypatch.setenv("MINERU_BIN", str(mineru_bin))
    monkeypatch.setenv("MINERU_FORCE_ARM64", "1")
    monkeypatch.setattr("questionbank.mineru_adapter.subprocess.run", fake_run)

    run_mineru_parse(pdf_path, output_dir=output_dir)

    assert calls[0][:3] == ["/usr/bin/arch", "-arm64", str(mineru_bin)]


def test_run_mineru_parse_wraps_timeout_as_mineru_error(tmp_path, monkeypatch):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    mineru_bin = tmp_path / "mineru"
    mineru_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    mineru_bin.chmod(0o755)

    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs["timeout"])

    monkeypatch.setenv("MINERU_BIN", str(mineru_bin))
    monkeypatch.setenv("MINERU_FORCE_ARM64", "0")
    monkeypatch.setattr("questionbank.mineru_adapter.subprocess.run", fake_run)

    try:
        run_mineru_parse(pdf_path, output_dir=tmp_path / "out", timeout_seconds=1)
    except MinerUExecutionError as exc:
        assert "timed out" in str(exc)
    else:
        raise AssertionError("expected MinerUExecutionError")


def test_read_mineru_text_prefers_content_list_text(tmp_path):
    content_list = tmp_path / "paper_content_list.json"
    content_list.write_text(
        json.dumps(
            [
                {"type": "text", "text": "Question 1"},
                {"type": "equation", "text": "$x^2$"},
                {"type": "table", "table_body": "<table><tr><td>2</td></tr></table>"},
            ]
        ),
        encoding="utf-8",
    )
    markdown = tmp_path / "paper.md"
    markdown.write_text("fallback", encoding="utf-8")

    class Result:
        content_list_path = content_list
        content_list_v2_path = None
        markdown_path = markdown

    assert read_mineru_text(Result()) == "Question 1\n\n$x^2$\n\n<table><tr><td>2</td></tr></table>"


def test_read_mineru_text_falls_back_to_markdown(tmp_path):
    markdown = tmp_path / "paper.md"
    markdown.write_text("markdown text", encoding="utf-8")

    class Result:
        content_list_path = None
        content_list_v2_path = None
        markdown_path = markdown

    assert read_mineru_text(Result()) == "markdown text"
