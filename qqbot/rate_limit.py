from __future__ import annotations

import hashlib
import math
import time
from pathlib import Path


IMAGE_PARSE_INTERVAL_SECONDS = 30
IMAGE_RATE_LIMIT_DIR = Path(__file__).resolve().parent.parent / ".cache" / "image_rate_limit"


def _sender_cache_path(sender_id: str) -> Path:
    digest = hashlib.sha256(sender_id.encode("utf-8")).hexdigest()
    return IMAGE_RATE_LIMIT_DIR / f"{digest}.txt"


def check_image_parse_rate_limit(sender_id: str | None) -> int:
    if not sender_id:
        sender_id = "unknown"

    now = time.time()
    IMAGE_RATE_LIMIT_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = _sender_cache_path(sender_id)

    try:
        last_sent_at = float(cache_path.read_text(encoding="utf-8").strip())
    except (FileNotFoundError, ValueError):
        last_sent_at = 0

    elapsed = now - last_sent_at
    if elapsed < IMAGE_PARSE_INTERVAL_SECONDS:
        return max(1, math.ceil(IMAGE_PARSE_INTERVAL_SECONDS - elapsed))

    cache_path.write_text(str(now), encoding="utf-8")
    return 0
