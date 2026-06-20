"""Test margin-column fix on stats Ex2 photo."""
from __future__ import annotations
import io, json, logging, os, sys, time
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).with_name(".env"), override=True)

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
for n in ("httpx","httpcore","urllib3","openai"):
    logging.getLogger(n).setLevel(logging.WARNING)

from PIL import Image
from pipeline.segmenter import segment_and_extract
from router.models import ModelRole, OpenAICompatClient


def main():
    img_path = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/latest_upload_2.jpeg")
    img = Image.open(img_path).convert("RGB")
    print(f"loaded image {img.size} from {img_path}")

    os.environ["SEGMENT_STITCH_PAGES"] = "1"
    model_id = os.environ.get("VISION_MODEL", "qwen3-vl-plus")
    client = OpenAICompatClient(
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model_id=model_id, provider="probe", role=ModelRole.vision,
        api_key=os.environ["DASHSCOPE_API_KEY"], timeout=120)

    t0 = time.monotonic()
    res = segment_and_extract([img], client, ocr_client=None)
    dt = time.monotonic() - t0
    print(f"\n[{model_id}] {len(res)} items in {dt:.1f}s\n")

    for r in res:
        qn = r.get("question_number")
        sa = (r.get("student_answer") or "").replace("\n"," ")[:80]
        ws = r.get("working_steps") or []
        flag = "⚑" if r.get("needs_review") else " "
        is_ex = "EX" if r.get("is_example") else "  "
        print(f" {flag} {is_ex} Q{qn!s:<12s} sa={sa!r:<65s} ws:{len(ws)}")

    out = Path(f"/tmp/stats_ex2.{model_id}.json")
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2))
    print(f"\nsaved → {out}")
    print(f"WALL-CLOCK: {dt:.1f}s")


if __name__ == "__main__":
    main()
