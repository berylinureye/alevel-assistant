from __future__ import annotations

from pathlib import Path

import pytest

from parser import pdf_parser
from questionbank.mineru_adapter import MinerUNotAvailableError, MinerUResult


def _paper(tmp_path: Path) -> Path:
    path = tmp_path / "9709_s22_qp_11.pdf"
    path.write_bytes(b"%PDF-1.4\n")
    return path


def test_parse_question_paper_uses_mineru_text_when_enabled(tmp_path, monkeypatch):
    paper = _paper(tmp_path)
    seen: dict[str, object] = {}

    def fake_run_mineru_parse(path, **kwargs):
        seen["mineru_path"] = Path(path)
        return MinerUResult(input_path=Path(path), output_dir=tmp_path)

    def fake_read_mineru_text(result):
        return "1 Find the value of x. [2]"

    def fake_extract_from_text(text, prompt, client=None):
        seen["text"] = text
        seen["client"] = client
        return [
            {
                "question_number": "1",
                "question_text": "Find the value of $x$.",
                "marks": 2,
                "topic": "algebra_p2",
                "subtopic": "linear_equations",
                "difficulty": 1,
                "tags": ["linear_equations"],
                "page": 1,
            }
        ]

    monkeypatch.setattr(pdf_parser, "run_mineru_parse", fake_run_mineru_parse)
    monkeypatch.setattr(pdf_parser, "read_mineru_text", fake_read_mineru_text)
    monkeypatch.setattr(pdf_parser, "extract_questions_from_text_with_ai", fake_extract_from_text)
    monkeypatch.setattr(
        pdf_parser,
        "pdf_to_images",
        lambda *args, **kwargs: pytest.fail("image extraction should not run"),
    )

    client = object()
    items = pdf_parser.parse_question_paper(paper, client=client, use_mineru=True)

    assert seen["mineru_path"] == paper
    assert seen["text"] == "1 Find the value of x. [2]"
    assert seen["client"] is client
    assert len(items) == 1
    assert items[0].question_number == "1"
    assert items[0].topic == "algebra_p2"
    assert items[0].tags == ["linear_equations"]


def test_parse_question_paper_falls_back_when_mineru_unavailable(tmp_path, monkeypatch):
    paper = _paper(tmp_path)

    def fake_run_mineru_parse(path, **kwargs):
        raise MinerUNotAvailableError("missing")

    monkeypatch.setattr(pdf_parser, "run_mineru_parse", fake_run_mineru_parse)
    monkeypatch.setattr(pdf_parser, "pdf_to_images", lambda *args, **kwargs: ["cover", "page"])
    monkeypatch.setattr(
        pdf_parser,
        "extract_questions_with_ai",
        lambda images, prompt, client=None: [
            {
                "question_number": "1",
                "question_text": "Fallback question",
                "marks": 1,
                "topic": "quadratics",
                "difficulty": 2,
            }
        ],
    )

    items = pdf_parser.parse_question_paper(paper, use_mineru=True)

    assert len(items) == 1
    assert items[0].question_text == "Fallback question"
    assert items[0].topic == "quadratics"


def test_parse_question_paper_can_require_mineru(tmp_path, monkeypatch):
    paper = _paper(tmp_path)

    def fake_run_mineru_parse(path, **kwargs):
        raise MinerUNotAvailableError("missing")

    monkeypatch.setattr(pdf_parser, "run_mineru_parse", fake_run_mineru_parse)

    with pytest.raises(MinerUNotAvailableError):
        pdf_parser.parse_question_paper(paper, use_mineru=True, require_mineru=True)


def test_parse_question_paper_can_skip_mark_scheme(tmp_path, monkeypatch):
    paper = _paper(tmp_path)
    ms_path = tmp_path / "9709_s22_ms_11.pdf"
    ms_path.write_bytes(b"%PDF-1.4\n")

    monkeypatch.setattr(
        pdf_parser,
        "run_mineru_parse",
        lambda path, **kwargs: MinerUResult(input_path=Path(path), output_dir=tmp_path),
    )
    monkeypatch.setattr(pdf_parser, "read_mineru_text", lambda result: "1 Find x. [1]")
    monkeypatch.setattr(
        pdf_parser,
        "extract_questions_from_text_with_ai",
        lambda text, prompt, client=None: [
            {
                "question_number": "1",
                "question_text": "Find $x$.",
                "marks": 1,
                "topic": "quadratics",
                "subtopic": "quadratic_graphs",
                "difficulty": 1,
                "tags": ["quadratic_graphs"],
            }
        ],
    )
    monkeypatch.setattr(
        pdf_parser,
        "pdf_to_images",
        lambda *args, **kwargs: pytest.fail("mark scheme images should not be parsed"),
    )

    items = pdf_parser.parse_question_paper(
        paper,
        ms_path=ms_path,
        use_mineru=True,
        include_mark_scheme=False,
    )

    assert len(items) == 1
    assert items[0].correct_answer is None


def test_parse_json_from_response_repairs_unescaped_latex_array():
    response = r"""```json
[
  {
    "question_number": "1",
    "question_text": "Find $\sin x$.",
    "tags": ["integration_by_substitution"]
  }
]
```"""

    parsed = pdf_parser._parse_json_from_response(response)

    assert parsed[0]["question_number"] == "1"
    assert parsed[0]["tags"] == ["integration_by_substitution"]
