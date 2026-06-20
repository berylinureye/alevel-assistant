"""
五路视觉模型对同一份 PDF 的切题/抽取对比。
启用拼图（SEGMENT_STITCH_PAGES=1），关 OCR 回写。每个模型的输出保存为单独 JSON。
用法：python test_segmenter_glm.py [pdf_path]
"""
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


def pdf_to_images(p: Path) -> list[Image.Image]:
    doc = fitz.open(p)
    return [Image.open(io.BytesIO(pg.get_pixmap(dpi=150).tobytes("png"))).convert("RGB") for pg in doc]


MODELS = [
    # (tag, base_url, env_key_var, model_id)
    ("qwen-vl-max",          "https://dashscope.aliyuncs.com/compatible-mode/v1", "DASHSCOPE_API_KEY", "qwen-vl-max"),
    ("qwen3-vl-plus",        "https://dashscope.aliyuncs.com/compatible-mode/v1", "DASHSCOPE_API_KEY", "qwen3-vl-plus"),
    ("glm-4.5v",             "https://open.bigmodel.cn/api/paas/v4",               "GLM_API_KEY",       "glm-4.5v"),
    ("glm-5",                "https://open.bigmodel.cn/api/paas/v4",               "GLM_API_KEY",       "glm-5"),
    ("doubao-seed-1.6-vision","https://ark.cn-beijing.volces.com/api/v3",          "DOUBAO_API_KEY",    "doubao-seed-1-6-vision-250815"),
]


def summarize(tag: str, res: list[dict]) -> None:
    print(f"\n======= {tag} ({len(res)} questions) =======")
    for r in res:
        qn = r.get("question_number")
        sa = (r.get("student_answer") or "").replace("\n"," ")[:90]
        ws = r.get("working_steps") or []
        flag = "⚑" if r.get("needs_review") else " "
        print(f" {flag} Q{qn}  sa={sa!r}  (ws:{len(ws)})")


def run_one(tag: str, base_url: str, key: str, model_id: str, imgs: list[Image.Image]) -> list[dict] | None:
    if not key:
        print(f"[skip {tag}] missing API key")
        return None
    client = OpenAICompatClient(base_url=base_url, model_id=model_id,
                                provider="probe", role=ModelRole.vision,
                                api_key=key, timeout=120)
    t0 = time.monotonic()
    try:
        res = segment_and_extract(imgs, client, ocr_client=None)
    except Exception as e:
        print(f"[error {tag}] {e}")
        return None
    print(f"[{tag}] {len(res)} questions in {time.monotonic()-t0:.1f}s")
    return res


def main():
    pdf = Path(sys.argv[1] if len(sys.argv) > 1 else "test/Lesson2-Coordinate geometry 11.pdf")
    if not pdf.exists():
        print(f"not found: {pdf}"); sys.exit(1)

    imgs = pdf_to_images(pdf)
    print(f"loaded {len(imgs)} pages from {pdf.name}")
    os.environ["SEGMENT_STITCH_PAGES"] = "1"

    all_results: dict[str, list[dict]] = {}
    for tag, url, key_var, mid in MODELS:
        key = os.environ.get(key_var, "").strip()
        res = run_one(tag, url, key, mid, imgs)
        if res is not None:
            all_results[tag] = res
            out = pdf.with_suffix(f".{tag}.json")
            out.write_text(json.dumps(res, ensure_ascii=False, indent=2))
            print(f"  saved → {out}")

    for tag, res in all_results.items():
        summarize(tag, res)

    # 并列对比关键题
    print("\n\n====== cross-model comparison on key questions ======")
    key_qs = ["1a","1b","1c","1d","2a","2b","3a","3b","3c","4a","4b","4c"]
    for kq in key_qs:
        print(f"\n── Q{kq}")
        for tag, res in all_results.items():
            match = [r for r in res if str(r.get("question_number","")).replace(" ","").lower().strip("()") in (kq, kq.replace("a","(a)").replace("b","(b)").replace("c","(c)").replace("d","(d)"))]
            # fuzzy match: strip punctuation
            if not match:
                match = [r for r in res if kq.replace("a","").replace("b","").replace("c","").replace("d","") in str(r.get("question_number","")) and kq[-1] in str(r.get("question_number",""))]
            if match:
                r = match[0]
                sa = (r.get("student_answer") or "")[:70]
                flag = "⚑" if r.get("needs_review") else " "
                print(f"   {flag} {tag:28s} sa={sa!r}")
            else:
                print(f"     {tag:28s} (not found)")


if __name__ == "__main__":
    main()
