"""Build a deterministic JPEG benchmark corpus from local upload fixtures."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except Exception:
    pillow_heif = None


DEFAULT_SOURCES = [
    Path("static/demo-input.jpg"),
    Path("test/IMG_BED71913-F089-4A0F-8813-33FC50873BF3.JPEG"),
    Path("test/IMG_FFDCA86C-D851-4C2A-B40C-38749536F898.JPEG"),
    Path("test/IMG_B1005BE1-7A67-4E7D-A56C-7B24AA0D0171.JPEG"),
    Path("test/IMG_D49734AE-67A1-42A9-B5FB-73810AA97748.JPEG"),
    Path("test/微信图片_20260407170227_46_4.jpg"),
    Path("test/微信图片_20260407164318_22_1047.jpg"),
    Path("test/微信图片_20260407170127_45_4.jpg"),
]

CATEGORY_SEQUENCE = (
    "normal",
    "normal",
    "low_clarity",
    "tilted_shadow",
    "cross_page",
    "blank_edge",
)


def _load_source(path: Path) -> Image.Image:
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
    image.thumbnail((1800, 2400), Image.Resampling.LANCZOS)
    return image


def _normal(image: Image.Image, index: int) -> Image.Image:
    output = image.copy()
    if index % 2:
        output = ImageEnhance.Contrast(output).enhance(1.05)
    return output


def _low_clarity(image: Image.Image, index: int) -> Image.Image:
    output = image.filter(ImageFilter.GaussianBlur(radius=1.1 + (index % 3) * 0.35))
    output = ImageEnhance.Contrast(output).enhance(0.78)
    output = ImageEnhance.Brightness(output).enhance(0.92)
    return output


def _tilted_shadow(image: Image.Image, index: int) -> Image.Image:
    angle = [-4, 3, -2, 5][index % 4]
    output = image.rotate(angle, expand=True, fillcolor=(242, 242, 238))
    overlay = Image.new("RGBA", output.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    width, height = output.size
    alpha = 45 + (index % 3) * 12
    draw.polygon(
        [(0, 0), (width, 0), (width, int(height * 0.45)), (0, int(height * 0.25))],
        fill=(0, 0, 0, alpha),
    )
    return Image.alpha_composite(output.convert("RGBA"), overlay).convert("RGB")


def _cross_page(image: Image.Image, index: int) -> Image.Image:
    width, height = image.size
    if index % 2:
        box = (0, int(height * 0.38), width, height)
    else:
        box = (0, 0, width, int(height * 0.72))
    crop = image.crop(box)
    canvas = Image.new("RGB", (width, height), "white")
    y = 0 if index % 2 == 0 else height - crop.size[1]
    canvas.paste(crop, (0, y))
    draw = ImageDraw.Draw(canvas)
    draw.line((0, y, width, y), fill=(225, 225, 225), width=3)
    return canvas


def _blank_edge(image: Image.Image, index: int) -> Image.Image:
    width, height = image.size
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    if index % 2:
        draw.text((max(20, width // 12), max(20, height // 12)), "Answer page only / no working shown", fill=(70, 70, 70))
        draw.text((max(20, width // 12), max(70, height // 12 + 55)), "Final answer: x = 3", fill=(70, 70, 70))
    else:
        draw.rectangle((width - width // 5, 0, width, height), fill=(248, 248, 248))
        draw.text((max(20, width // 14), max(20, height // 10)), "Blank / incomplete upload", fill=(90, 90, 90))
    return canvas


TRANSFORMS = {
    "normal": _normal,
    "low_clarity": _low_clarity,
    "tilted_shadow": _tilted_shadow,
    "cross_page": _cross_page,
    "blank_edge": _blank_edge,
}


def build_jpeg_corpus(
    *,
    sources: list[Path],
    output_dir: Path,
    count: int = 30,
) -> dict[str, Any]:
    if count <= 0:
        raise ValueError("count must be positive")
    resolved_sources = [Path(source) for source in sources if Path(source).exists()]
    if not resolved_sources:
        raise FileNotFoundError("No source images found for JPEG corpus generation")

    output_dir.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, Any]] = []
    for index in range(count):
        source = resolved_sources[index % len(resolved_sources)]
        category = CATEGORY_SEQUENCE[index % len(CATEGORY_SEQUENCE)]
        image = _load_source(source)
        transformed = TRANSFORMS[category](image, index)
        filename = f"{index + 1:02d}_{category}_{source.stem[:32]}.jpg"
        destination = output_dir / filename
        transformed.save(destination, format="JPEG", quality=86, optimize=True)
        items.append(
            {
                "index": index + 1,
                "filename": filename,
                "category": category,
                "source": str(source),
                "width": transformed.size[0],
                "height": transformed.size[1],
                "size_bytes": destination.stat().st_size,
            }
        )

    category_counts: dict[str, int] = {}
    for item in items:
        category_counts[item["category"]] = category_counts.get(item["category"], 0) + 1

    manifest = {
        "count": len(items),
        "category_counts": category_counts,
        "items": items,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a deterministic JPEG upload benchmark corpus.")
    parser.add_argument("--output-dir", default="test/fixtures/jpeg_benchmark_corpus")
    parser.add_argument("--count", type=int, default=30)
    parser.add_argument("--source", action="append", dest="sources", help="Source image path. Can be passed multiple times.")
    args = parser.parse_args()

    sources = [Path(source) for source in args.sources] if args.sources else DEFAULT_SOURCES
    manifest = build_jpeg_corpus(sources=sources, output_dir=Path(args.output_dir), count=max(1, args.count))
    print(json.dumps({"status": "ok", "output_dir": args.output_dir, **manifest}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
