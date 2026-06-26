"""图像加载、裁剪、base64 编码工具"""
from __future__ import annotations

import base64
import io
import logging
import os
from PIL import Image, ImageOps

_log = logging.getLogger(__name__)

MAX_DIMENSION = 2048
JPEG_QUALITY = 85


def _env_flag(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _register_optional_image_openers() -> None:
    """Enable HEIC/HEIF support when pillow-heif is available."""
    try:
        from pillow_heif import register_heif_opener
    except Exception as exc:
        _log.debug("HEIF support unavailable: %s", exc)
        return
    register_heif_opener()


_register_optional_image_openers()


def load_image(path: str) -> Image.Image:
    img = Image.open(path)
    img = ImageOps.exif_transpose(img).convert("RGB")
    # 若 tesseract 可用，尝试本地朝向检测并旋转（处理横拍/倒置的作业照片）
    img = try_auto_orient_via_osd(img)
    w, h = img.size
    if max(w, h) > MAX_DIMENSION:
        scale = MAX_DIMENSION / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    return img


def try_auto_orient_via_osd(image: Image.Image) -> Image.Image:
    """
    使用 tesseract OSD（若已安装）做一次本地朝向检测并旋转。
    不依赖网络、不增加 AI 调用。tesseract 未装时静默返回原图。
    """
    if not _env_flag("IMAGE_OSD_ENABLED"):
        return image
    try:
        import pytesseract
        timeout = float(os.environ.get("IMAGE_OSD_TIMEOUT_SECONDS", "1.5"))
        osd = pytesseract.image_to_osd(image, timeout=max(0.1, timeout))
        import re
        m = re.search(r"Rotate:\s*(\d+)", osd)
        if m:
            angle = int(m.group(1))
            if angle in (90, 180, 270):
                return image.rotate(-angle, expand=True, resample=Image.BICUBIC)
    except Exception:
        pass
    return image


def crop_region(image: Image.Image, bbox: list[int]) -> Image.Image:
    """bbox = [x1, y1, x2, y2]"""
    return image.crop((bbox[0], bbox[1], bbox[2], bbox[3]))


def image_to_base64(image: Image.Image, fmt: str = "JPEG") -> str:
    buf = io.BytesIO()
    save_kwargs: dict = {"format": fmt}
    if fmt.upper() == "JPEG":
        save_kwargs.update({
            "quality": JPEG_QUALITY,
            "optimize": True,
            "subsampling": 0,
        })
    image.save(buf, **save_kwargs)
    return base64.standard_b64encode(buf.getvalue()).decode("utf-8")


def clamp_bbox(bbox: list[int], width: int, height: int) -> list[int]:
    x1, y1, x2, y2 = (int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3]))
    x1 = max(0, min(x1, width))
    y1 = max(0, min(y1, height))
    x2 = max(0, min(x2, width))
    y2 = max(0, min(y2, height))

    # 兜底：避免出现反向 bbox（x2<x1 或 y2<y1）导致 crop 异常/空图
    if x2 < x1:
        x1, x2 = x2, x1
    if y2 < y1:
        y1, y2 = y2, y1

    # 兜底：避免退化为 0 宽/0 高（至少给 1px）
    if x2 == x1 and width > 0:
        x2 = min(width, x1 + 1)
    if y2 == y1 and height > 0:
        y2 = min(height, y1 + 1)

    return [x1, y1, x2, y2]


def pad_bbox(bbox: list[int], width: int, height: int, pad_ratio: float = 0.05) -> list[int]:
    """Expand bbox by pad_ratio in all directions, then clamp to image bounds."""
    x1, y1, x2, y2 = bbox
    bw = x2 - x1
    bh = y2 - y1
    px = int(bw * pad_ratio)
    py = int(bh * pad_ratio)
    return clamp_bbox([x1 - px, y1 - py, x2 + px, y2 + py], width, height)
