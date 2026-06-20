"""
Extractor：单题裁图 → QuestionData

可升级点：
  - question_text / working_steps 可替换成 Mathpix 等专用数学 OCR
  - image_quality / confidence 可替换成专用图像质量评估模型
"""
from __future__ import annotations

import json
import logging
import re

from models.schemas import QuestionData, QuestionSegment
from router.models import ModelClient, ModelRequest, TaskType
from utils.image_utils import image_to_base64

_EXTRACT_PROMPT = """\
You are analyzing a cropped image of a single question from a student's A-Level math homework.

The image may contain:
- PRINTED text (the question itself — typed font)
- HANDWRITTEN text in PENCIL (student's working and answer — may be faint/light)
- HANDWRITTEN text in PEN, including RED PEN (could be student's own work or teacher marks)
- Crossed-out or corrected work (still extract it, note as corrected)

IMPORTANT: Pay special attention to PENCIL marks which may be faint. Students often write
their working steps and final answers in pencil. Do NOT skip content just because it is light.

If there are RED PEN marks that appear to be teacher corrections (e.g., checkmarks, crosses,
circled errors, written corrections), note them but focus on extracting the STUDENT's original work.

Extract the following and return ONLY a valid JSON object — no markdown, no explanation:
{{
  "question_text": "<the full question being asked, including given conditions, equations, instructions>",
  "student_answer": "<the final answer the student wrote — just the conclusion, not the working>",
  "working_steps": ["<step 1>", "<step 2>", ...],
  "image_quality": "<good | fair | poor>",
  "confidence": <float 0.0-1.0>
}}

Guidelines:
- question_text: transcribe the printed question text. Wrap all mathematical expressions in dollar signs: $dy/dx$, $x^2 + 3x - 4 = 0$. Plain text descriptions should NOT be wrapped.
- student_answer: the student's FINAL answer (usually at the end of their working, possibly underlined or boxed); wrap math in $...$ as above
- working_steps: each entry is one meaningful calculation or logical step the student wrote; each step should wrap math in $...$. Example: 'Differentiating both sides: $\\frac{dy}{dx} = 3x^2 - 2$'
  - Include ALL visible steps, even if handwriting is hard to read
  - If a step is unclear, append "(unclear)" but still include your best reading of it
  - If a step appears crossed out, prefix with "(crossed out)" 
- image_quality: good = all text legible, fair = some parts hard to read, poor = mostly illegible
- confidence: your confidence that you correctly read ALL the handwritten content (lower if pencil is faint)
"""


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        return match.group(1).strip()
    return text


def _extract_json_object(text: str) -> str | None:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start : end + 1].strip()


def _cleanup_common_json_issues(text: str) -> str:
    text = re.sub(r",\s*([}\]])", r"\1", text)
    text = text.replace("“", '"').replace("”", '"').replace("’", "'")
    return text


def _parse_json(text: str) -> dict:
    raw = _strip_code_fence(text)
    candidates: list[str] = [raw]
    extracted = _extract_json_object(raw)
    if extracted and extracted != raw:
        candidates.insert(0, extracted)

    last_err: Exception | None = None
    for cand in candidates:
        try:
            return json.loads(_cleanup_common_json_issues(cand))
        except Exception as e:
            last_err = e
            continue
    raise ValueError(f"Model output is not valid JSON object: {last_err}") from last_err


def extract_question(
    segment: QuestionSegment,
    client: ModelClient,
) -> QuestionData:
    assert client.supports_images(), "extractor requires a client that supports images"

    b64 = image_to_base64(segment.cropped_image)
    base_prompt = _EXTRACT_PROMPT
    request = ModelRequest(
        task=TaskType.extract,
        prompt=base_prompt,
        images=[b64],
        max_tokens=2048,
    )
    last_err: Exception = RuntimeError("no attempts made")
    data: dict | None = None
    for attempt in range(3):
        try:
            raw = client.call(request)
            data = _parse_json(raw)
            break
        except Exception as e:
            last_err = e
            logging.getLogger("pipeline.extractor").warning(
                "extract attempt %d/3 failed for Q%s: %s", attempt + 1, segment.question_number, e,
            )
            request = ModelRequest(
                task=TaskType.extract,
                images=[b64],
                max_tokens=2048,
                prompt=(
                    "IMPORTANT: Return ONLY a valid JSON object. "
                    "No markdown, no code fences, no extra text.\n\n"
                    + base_prompt
                ),
            )
    if data is None:
        logging.getLogger("pipeline.extractor").warning(
            "extraction failed after 3 attempts for Q%s: %s",
            segment.question_number, last_err,
        )
        return QuestionData(
            question_number=segment.question_number,
            bbox=segment.bbox,
            question_text="",
            student_answer="",
            working_steps=[],
            image_quality="poor",
            confidence=0.0,
        )

    question_text = data.get("question_text") or ""
    student_answer = data.get("student_answer") or ""
    working_steps_raw = data.get("working_steps") or []
    if not isinstance(working_steps_raw, list):
        working_steps_raw = []
    working_steps = [str(s) for s in working_steps_raw if s is not None]

    image_quality = data.get("image_quality") or "fair"
    try:
        confidence = float(data.get("confidence", 0.5) or 0.5)
    except Exception:
        confidence = 0.5

    return QuestionData(
        question_number=segment.question_number,
        bbox=segment.bbox,
        question_text=str(question_text),
        student_answer=str(student_answer),
        working_steps=working_steps,
        image_quality=str(image_quality),
        confidence=confidence,
    )
