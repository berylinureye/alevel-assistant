"""CLI 入口

用法:
    python main.py <image_path>
    python main.py <image_path> --output result.json
"""
from __future__ import annotations

import argparse
import json
import sys
from dotenv import load_dotenv

from pipeline.pipeline import run_pipeline


def main() -> None:
    load_dotenv(override=True)

    parser = argparse.ArgumentParser(
        description="A-Level 作业助手 — 作业图片 → 结构化 JSON"
    )
    parser.add_argument("image_path", help="作业图片路径（jpg/png）")
    parser.add_argument(
        "--output", "-o", help="输出 JSON 文件路径（不指定则打印到 stdout）"
    )
    args = parser.parse_args()

    try:
        results = run_pipeline(args.image_path)
    except Exception as e:
        print(f"[error] {e}", file=sys.stderr)
        sys.exit(1)

    output = json.dumps(results, ensure_ascii=False, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"[done] 结果已写入 {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
