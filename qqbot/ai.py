import base64
from io import BytesIO
import json
import os
import re
from typing import Any

import httpx
from dotenv import load_dotenv
from PIL import Image, ImageOps

load_dotenv()

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

VISION_MODEL = os.getenv("VISION_MODEL", "google/gemini-flash-1.5")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

EXTRACT_IMG_SYSTEM_PROMPT = (
    "提取图片中用户首次评价的日期与内容，以最上面一条为准。严格输出一个字段为date和content的JSON。如找不到，输出空JSON。严禁编造或输出任何其他内容。"
)

MAX_VISION_IMAGE_WIDTH = 540
VISION_IMAGE_JPEG_QUALITY = 85


def _repair_json(text: str) -> dict[str, Any]:
    """Extract and parse the first JSON object found in text."""
    text = re.sub(r"```(?:json)?", "", text).strip()
    match = re.search(r"\{.*?\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in response: {text!r}")
    return json.loads(match.group())


def _resize_image_for_vision(image_url: str, max_width: int = MAX_VISION_IMAGE_WIDTH) -> str:
    """Download an image URL, resize it proportionally, and return a JPEG data URL."""
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        response = client.get(image_url)
        response.raise_for_status()

    with Image.open(BytesIO(response.content)) as image:
        image = ImageOps.exif_transpose(image)
        if image.width > max_width:
            ratio = max_width / image.width
            image = image.resize(
                (max_width, max(1, round(image.height * ratio))),
                Image.Resampling.LANCZOS,
            )

        if image.mode not in ("RGB", "L"):
            background = Image.new("RGB", image.size, (255, 255, 255))
            if "A" in image.getbands():
                background.paste(image, mask=image.getchannel("A"))
                image = background
            else:
                image = image.convert("RGB")
        else:
            image = image.convert("RGB")

        output = BytesIO()
        image.save(output, format="JPEG", quality=VISION_IMAGE_JPEG_QUALITY, optimize=True)

    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def extract_img(image_url: str) -> dict[str, str] | None:
    """Call vision model to extract the first review date and content from an image URL.

    Returns a dict with 'date' and 'content' keys, or None if no review was found.
    """
    image_data_url = _resize_image_for_vision(image_url)
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": VISION_MODEL,
        "messages": [
            {"role": "system", "content": EXTRACT_IMG_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": image_data_url},
                    }
                ],
            },
        ],
    }
    with httpx.Client(timeout=60) as client:
        resp = client.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()

    raw = resp.json()["choices"][0]["message"]["content"]
    result = _repair_json(raw)
    # Empty JSON {} means the model found no review
    if not result.get("date") and not result.get("content"):
        return None
    return result


def embedding(text: str, dimensions: int = 384) -> list[float]:
    """Return embedding vector for the given text (default 384 dimensions)."""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "model": EMBEDDING_MODEL,
        "input": text,
    }
    # Some models support custom dimensions
    if dimensions != 1536:
        payload["dimensions"] = dimensions

    with httpx.Client(timeout=30) as client:
        resp = client.post(
            f"{OPENROUTER_BASE_URL}/embeddings",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()

    return resp.json()["data"][0]["embedding"]
