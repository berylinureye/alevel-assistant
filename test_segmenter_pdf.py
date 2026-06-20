"""
只跑 segmenter（不走 grading），对比拼图前后对 PDF 的识别差异。
用法：python test_segmenter_pdf.py [pdf_path]
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

import fitz  # pymupdf
from PIL import Image
import io

from pipeline.segmenter import segment_and_extract
from router.models import build_registry, ModelRole


def pdf_to_images(pdf_path: Path) -> list[Image.Image]:
    doc = fitz.open(pdf_path)
    imgs: list[Image.Image] = []
    for page in doc:
        pix = page.get_pixmap(dpi=150)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        imgs.append(img)
    return imgs


def summarize(results: list[dict]) -> None:
    print(f"\n# questions extracted: {len(results)}\n")
    for r in results:
        qn = r.get("question_number")
        qt = (r.get("question_text") or "").replace("\n", " ")
        sa = (r.get("student_answer") or "").replace("\n", " ")
        ws = r.get("working_steps") or []
        marks = r.get("marks")
        page = r.get("page")
        conf = r.get("confidence")
        print(f"── Q{qn}  page={page}  marks={marks}  conf={conf:.2f}")
        print(f"   question_text : {qt[:180]}")
        print(f"   student_answer: {sa[:180]}")
        if ws:
            print(f"   working_steps : {len(ws)} step(s):")
            for s in ws[:6]:
                print(f"     - {str(s)[:160]}")
        print()


def main():
    pdf = Path(sys.argv[1] if len(sys.argv) > 1 else
               "test/Lesson2-Coordinate geometry 11.pdf")
    if not pdf.exists():
        print(f"not found: {pdf}")
        sys.exit(1)

    imgs = pdf_to_images(pdf)
    print(f"loaded {len(imgs)} pages from {pdf.name}")

    registry = build_registry()
    vision = registry.get(ModelRole.vision, registry[ModelRole.base])
    ocr = registry.get(ModelRole.ocr)

    # run A: with stitching (default)
    os.environ["SEGMENT_STITCH_PAGES"] = "1"
    print("\n======= A · stitched (方案 2 ON) =======")
    res_a = segment_and_extract(imgs, vision, ocr_client=ocr)
    summarize(res_a)

    # run B: without stitching (方案 1 only)
    os.environ["SEGMENT_STITCH_PAGES"] = "0"
    print("\n======= B · no stitch, merge only (方案 1 ONLY) =======")
    res_b = segment_and_extract(imgs, vision, ocr_client=ocr)
    summarize(res_b)

    # save both for diff
    out_a = pdf.with_suffix(".stitched.json")
    out_b = pdf.with_suffix(".mergeonly.json")
    out_a.write_text(json.dumps(res_a, ensure_ascii=False, indent=2))
    out_b.write_text(json.dumps(res_b, ensure_ascii=False, indent=2))
    print(f"\nsaved: {out_a}\nsaved: {out_b}")


if __name__ == "__main__":
    main()
