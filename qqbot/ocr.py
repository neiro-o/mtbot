from __future__ import annotations

from functools import lru_cache
from typing import Any

import httpx


MAX_OCR_IMAGE_WIDTH = 360
XIAOMEI_TRIGGER_SCORE = 5
XIAOMEI_POSITIVE_KEYWORDS = (
    "小美封审榜",
    "结果一致",
    "连续一致",
    "不适合展示",
    "用户评价",
    "商户回复",
    "商户证据",
)
XIAOMEI_NEGATIVE_KEYWORDS = (
    "选择与结果一致",
    "选择与结果不一致",
    "下一关",
)


@lru_cache(maxsize=1)
def _get_ocr_engine() -> Any:
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


def parse_image_url_with_ocr(image_url: str) -> tuple[list[list[Any]] | None, list[float] | None]:
    """Download an image URL and return RapidOCR's original result."""
    import cv2
    import numpy as np

    with httpx.Client(timeout=30, follow_redirects=True) as client:
        response = client.get(image_url)
        response.raise_for_status()

    image = cv2.imdecode(np.frombuffer(response.content, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("OCR image decode failed")

    height, width = image.shape[:2]
    if width > MAX_OCR_IMAGE_WIDTH:
        ratio = MAX_OCR_IMAGE_WIDTH / width
        image = cv2.resize(
            image,
            (MAX_OCR_IMAGE_WIDTH, int(height * ratio)),
            interpolation=cv2.INTER_AREA,
        )

    return _get_ocr_engine()(image, use_cls=False)


def count_xiaomei_keywords(image_url: str) -> int:
    """Score Xiaomei keywords from OCR lines in an image URL."""
    ocr_result, _ = parse_image_url_with_ocr(image_url)
    if not ocr_result:
        return 0

    lines = [str(item[1]) for item in ocr_result if len(item) >= 2]
    negative_lines = [
        line
        for line in lines
        if any(keyword in line for keyword in XIAOMEI_NEGATIVE_KEYWORDS)
    ]
    positive_lines = [line for line in lines if line not in negative_lines]

    positive_score = sum(
        1
        for keyword in XIAOMEI_POSITIVE_KEYWORDS
        if any(keyword in line for line in positive_lines)
    )
    negative_score = sum(
        1
        for keyword in XIAOMEI_NEGATIVE_KEYWORDS
        if any(keyword in line for line in negative_lines)
    )
    return positive_score - negative_score
