"""End-to-end sanity run with the new default VISION_MODEL=qwen3-vl-plus."""
from __future__ import annotations
import io, json, logging, os, sys, time
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).with_name(".env"), override=True)

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
for n in ("httpx","httpcore","urllib3","openai"):
    logging.getLogger(n).setLevel(logging.WARNING)

import fitz
from PIL import Image
from pipeline.segmenter import segment_and_extract
from router.models import ModelRole, OpenAICompatClient


def pdf_to_images(p: Path):
    doc = fitz.open(p)
    return [Image.open(io.BytesIO(pg.get_pixmap(dpi=150).tobytes("png"))).convert("RGB") for pg in doc]


def main():
    pdf = Path(sys.argv[1] if len(sys.argv) > 1 else "test/Lesson2-Coordinate geometry 11.pdf")
    imgs = pdf_to_images(pdf)
    print(f"loaded {len(imgs)} pages from {pdf.name}")
    os.environ["SEGMENT_STITCH_PAGES"] = "1"

    model_id = os.environ.get("VISION_MODEL", "qwen3-vl-plus")
    key = os.environ["DASHSCOPE_API_KEY"]
    client = OpenAICompatClient(
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model_id=model_id, provider="probe", role=ModelRole.vision,
        api_key=key, timeout=120)

    t0 = time.monotonic()
    res = segment_and_extract(imgs, client, ocr_client=None)
    dt = time.monotonic() - t0
    print(f"\n[{model_id}] {len(res)} questions in {dt:.1f}s (avg {dt/max(len(res),1):.1f}s/question)")

    out = pdf.with_suffix(f".{model_id}.default.json")
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2))
    print(f"saved → {out}\n")

    flagged = 0
    for r in res:
        qn = r.get("question_number")
        sa = (r.get("student_answer") or "").replace("\n"," ")[:80]
        ws = r.get("working_steps") or []
        flag = "⚑" if r.get("needs_review") else " "
        if r.get("needs_review"): flagged += 1
        print(f" {flag} Q{qn:<5s}  sa={sa!r:<75s}  ws:{len(ws)}")
    print(f"\ntotal questions: {len(res)}, flagged for review: {flagged}")
    print(f"WALL-CLOCK LATENCY: {dt:.1f}s")


if __name__ == "__main__":
    main()
