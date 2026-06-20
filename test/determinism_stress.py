"""
Determinism stress test for the segmenter's VL call.

Hypothesis under test: qwen3-vl-plus may produce different outputs across
runs for the same input PDF (same code, same config, same prompt), and
in particular may sometimes emit bridging sentences inside
``question_text`` instead of keeping them in ``parent_stem``.

What this does:
    * Runs ``segment_and_extract`` against a single PDF N times back-to-back
      (sequential — respects any client-side rate limits).
    * Each run writes its own set of dumps under test/segmenter_dumps/ via
      the env-gated hook, prefixed ``<pdf_stem>_detNN_...``.
    * After all runs, loads each raw dump for page 1, extracts the 1a
      item, and tabulates:
          - question_text byte-identity across runs
          - whether 1a's question_text contains trailing bridging
            substring "The point P(1, 2) lies on the circle"
            (Lesson2-specific sentinel)
          - whether 1a's parent_stem is the minimal pre-bridging version
            (starts with "The equation" and stops before "The point P")

Usage:
    python test/determinism_stress.py <pdf_path> [--n=10]

No production code is touched. Only the harness-level hook added earlier
in pipeline/segmenter.py (activated by SEGMENTER_DUMP_DIR env var) is used.
"""
from __future__ import annotations

import io
import json
import logging
import os
import sys
import time
from pathlib import Path

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

import fitz
from PIL import Image

from pipeline.segmenter import segment_and_extract
from router.models import build_registry, ModelRole


DUMP_DIR = Path("test/segmenter_dumps").resolve()
# Lesson2-specific sentinel: this is the bridging sentence that
# belongs to sub-part (b)'s setup, NOT to 1a's question_text.
# Its presence inside 1a.question_text === the exact user-reported bug.
BRIDGING_SENTINEL = "The point P(1, 2) lies on the circle"


def pdf_to_images(pdf_path: Path) -> list[Image.Image]:
    doc = fitz.open(pdf_path)
    out: list[Image.Image] = []
    for page in doc:
        pix = page.get_pixmap(dpi=150)
        out.append(Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB"))
    return out


def sanitize_stem(raw: str) -> str:
    return "_".join(raw.split())


def run_once(
    pdf_path: Path,
    imgs: list[Image.Image],
    vision,
    ocr,
    run_idx: int,
) -> None:
    stem = f"{sanitize_stem(pdf_path.stem)}_det{run_idx:02d}"
    os.environ["SEGMENTER_DUMP_DIR"] = str(DUMP_DIR)
    os.environ["SEGMENTER_DUMP_PREFIX"] = stem
    os.environ["SEGMENT_STITCH_PAGES"] = "1"
    t0 = time.perf_counter()
    _ = segment_and_extract(imgs, vision, ocr_client=ocr)
    print(f"  run {run_idx:02d}: {time.perf_counter() - t0:.1f}s  prefix={stem}")


def analyze(pdf_path: Path, n: int) -> None:
    stem = sanitize_stem(pdf_path.stem)
    rows: list[dict] = []
    qtexts_seen: dict[str, list[int]] = {}

    for i in range(1, n + 1):
        p = DUMP_DIR / f"{stem}_det{i:02d}_page1_raw.json"
        if not p.exists():
            rows.append({"run": i, "error": f"missing {p.name}"})
            continue
        try:
            items = json.loads(p.read_text())
        except Exception as e:
            rows.append({"run": i, "error": str(e)})
            continue
        one_a = next((it for it in items if str(it.get("question_number", "")).strip().lower() in ("1a", "1(a)")), None)
        if one_a is None:
            rows.append({"run": i, "error": "no 1a"})
            continue
        qt = one_a.get("question_text", "") or ""
        ps = one_a.get("parent_stem", "") or ""
        polluted = BRIDGING_SENTINEL in qt
        qtexts_seen.setdefault(qt, []).append(i)
        rows.append({
            "run": i,
            "qtext_len": len(qt),
            "pstem_len": len(ps),
            "polluted": polluted,
            "qtext_preview": (qt[:120] + "...") if len(qt) > 120 else qt,
            "pstem_preview": (ps[:80] + "...") if len(ps) > 80 else ps,
        })

    print("\n=== DETERMINISM STRESS RESULTS ===")
    for r in rows:
        if "error" in r:
            print(f"  run {r['run']:02d}: ERROR {r['error']}")
            continue
        flag = "🔴 POLLUTED" if r["polluted"] else "🟢 clean   "
        print(f"  run {r['run']:02d}: {flag}  qt_len={r['qtext_len']:3d}  ps_len={r['pstem_len']:3d}")
        print(f"          qt: {r['qtext_preview']!r}")
        print(f"          ps: {r['pstem_preview']!r}")

    ok_rows = [r for r in rows if "error" not in r]
    polluted = [r for r in ok_rows if r["polluted"]]
    print(f"\nSummary: {len(polluted)}/{len(ok_rows)} runs polluted "
          f"(contain {BRIDGING_SENTINEL!r} in 1a.question_text).")
    print(f"Unique 1a.question_text values seen: {len(qtexts_seen)}")
    for i, (qt, run_ids) in enumerate(qtexts_seen.items(), 1):
        print(f"  variant {i} (occurs in runs {run_ids}): len={len(qt)}")
        print(f"    {qt!r}")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    n = 10
    pdf_args: list[str] = []
    for a in sys.argv[1:]:
        if a.startswith("--n="):
            n = int(a.split("=", 1)[1])
        else:
            pdf_args.append(a)
    if not pdf_args:
        print("need pdf path"); sys.exit(1)
    pdf = Path(pdf_args[0])
    if not pdf.exists():
        print(f"not found: {pdf}"); sys.exit(1)

    DUMP_DIR.mkdir(parents=True, exist_ok=True)

    registry = build_registry()
    vision = registry.get(ModelRole.vision, registry[ModelRole.base])
    ocr = registry.get(ModelRole.ocr)
    print(f"vision: {getattr(vision, 'model_id', '?')}  ocr: {getattr(ocr, 'model_id', '?') if ocr else '-'}")
    print(f"running {n} iterations sequentially on {pdf.name}")

    imgs = pdf_to_images(pdf)
    print(f"rendered {len(imgs)} pages\n")

    t0 = time.perf_counter()
    for i in range(1, n + 1):
        try:
            run_once(pdf, imgs, vision, ocr, i)
        except Exception as e:
            logging.exception("run %d failed", i)
    print(f"\nall runs done in {time.perf_counter() - t0:.1f}s")

    analyze(pdf, n)


if __name__ == "__main__":
    main()
