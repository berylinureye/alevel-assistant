"""
Step 2 dump harness: run `segment_and_extract` against one or more PDFs,
collect per-page raw-VL + post-processed JSON snapshots via the env-gated
hook in pipeline/segmenter.py.

Usage:
    python test/dump_segmenter.py <pdf_path> [<pdf_path> ...]

    # minimum one PDF; multiple PDFs processed sequentially
    # e.g. python test/dump_segmenter.py "test/Lesson2-Coordinate geometry 11.pdf"

Output:
    test/segmenter_dumps/{pdf_stem}_page{N}_raw.json
    test/segmenter_dumps/{pdf_stem}_page{N}_postprocessed.json

`pdf_stem` is the filename without extension, with whitespace → underscores
so the resulting paths are shell-safe.

Behavior:
    * Does NOT modify segmenter logic — it only sets SEGMENTER_DUMP_DIR and
      SEGMENTER_DUMP_PREFIX env vars which activate the dump hook.
    * Runs in production-default mode (SEGMENT_STITCH_PAGES=1) so the VL
      output matches what real grading sees.
    * Prints a compact per-run summary (page count, items extracted, elapsed).

No assertions, no test framework: this is a diagnostic tool, not a test.
"""
from __future__ import annotations

import io
import logging
import os
import sys
import time
from pathlib import Path

# Ensure repo root is importable when running from inside test/
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

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

from pipeline.segmenter import segment_and_extract
from router.models import build_registry, ModelRole


DUMP_DIR = Path("test/segmenter_dumps").resolve()


def pdf_to_images(pdf_path: Path) -> list[Image.Image]:
    """Render each PDF page to a 150 DPI RGB PIL Image."""
    doc = fitz.open(pdf_path)
    imgs: list[Image.Image] = []
    for page in doc:
        pix = page.get_pixmap(dpi=150)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        imgs.append(img)
    return imgs


def sanitize_stem(raw: str) -> str:
    """Whitespace → underscore. Leave other chars alone; they're already
    fine for filenames on macOS."""
    return "_".join(raw.split())


def run_one(pdf_path: Path, vision_client, ocr_client, suffix: str = "") -> dict:
    """Process a single PDF, returning a summary dict (for the run log).

    ``suffix`` is appended to the sanitized stem so repeated runs on the
    same PDF don't clobber each other (useful for VL determinism checks,
    e.g. suffix='_rerun').
    """
    stem = sanitize_stem(pdf_path.stem) + suffix

    # Activate the env-gated dump hook in segmenter.py
    os.environ["SEGMENTER_DUMP_DIR"] = str(DUMP_DIR)
    os.environ["SEGMENTER_DUMP_PREFIX"] = stem
    # Production-default mode (stitch on) — mirror real grading path
    os.environ["SEGMENT_STITCH_PAGES"] = "1"

    print(f"\n=== {pdf_path.name} → prefix={stem} ===")
    t0 = time.perf_counter()
    imgs = pdf_to_images(pdf_path)
    print(f"rendered {len(imgs)} page(s) at 150 DPI")

    results = segment_and_extract(imgs, vision_client, ocr_client=ocr_client)
    elapsed = time.perf_counter() - t0

    # List resulting files so user sees what we produced
    produced = sorted(DUMP_DIR.glob(f"{stem}_*.json"))
    print(f"DONE in {elapsed:.1f}s — {len(results)} final item(s), "
          f"{len(produced)} dump file(s) written:")
    for p in produced:
        print(f"  {p.relative_to(DUMP_DIR.parent.parent) if p.is_absolute() else p}")

    return {
        "pdf": pdf_path.name,
        "prefix": stem,
        "pages_rendered": len(imgs),
        "final_items": len(results),
        "elapsed_s": round(elapsed, 1),
        "files_written": [p.name for p in produced],
    }


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    # Parse --suffix=... arg (anywhere on command line). Used for determinism
    # reruns so repeat dumps don't clobber the first.
    suffix = ""
    argv: list[str] = []
    for a in sys.argv[1:]:
        if a.startswith("--suffix="):
            suffix = a.split("=", 1)[1]
        else:
            argv.append(a)

    pdfs = [Path(p) for p in argv]
    for p in pdfs:
        if not p.exists():
            print(f"NOT FOUND: {p}")
            sys.exit(1)

    DUMP_DIR.mkdir(parents=True, exist_ok=True)
    print(f"dump dir: {DUMP_DIR}")

    registry = build_registry()
    vision = registry.get(ModelRole.vision, registry[ModelRole.base])
    ocr = registry.get(ModelRole.ocr)
    print(f"vision model: {getattr(vision, 'model_id', '?')}")
    print(f"ocr model   : {getattr(ocr, 'model_id', '?') if ocr else '<none>'}")

    summaries = []
    for pdf in pdfs:
        try:
            summaries.append(run_one(pdf, vision, ocr, suffix=suffix))
        except Exception as e:
            logging.exception("failed: %s", pdf)
            summaries.append({"pdf": pdf.name, "error": str(e)})

    print("\n=== RUN SUMMARY ===")
    for s in summaries:
        print(f"  {s}")


if __name__ == "__main__":
    main()
