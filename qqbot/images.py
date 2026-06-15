from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any

from botpy import logging


_log = logging.get_logger()

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp")


@dataclass(frozen=True)
class ImageAttachment:
    attachment_id: str | None
    content_type: str | None
    filename: str | None
    width: int | None
    height: int | None
    size: int | None
    url: str | None

    @classmethod
    def from_attachment(cls, attachment: Any) -> "ImageAttachment":
        return cls(
            attachment_id=getattr(attachment, "id", None),
            content_type=getattr(attachment, "content_type", None),
            filename=getattr(attachment, "filename", None),
            width=getattr(attachment, "width", None),
            height=getattr(attachment, "height", None),
            size=getattr(attachment, "size", None),
            url=getattr(attachment, "url", None),
        )


def is_image_attachment(attachment: Any) -> bool:
    content_type = (getattr(attachment, "content_type", "") or "").lower()
    filename = (getattr(attachment, "filename", "") or "").lower()
    url = (getattr(attachment, "url", "") or "").lower()

    return (
        content_type.startswith("image/")
        or filename.endswith(IMAGE_EXTENSIONS)
        or url.endswith(IMAGE_EXTENSIONS)
    )


def extract_image_attachments(message: Any) -> list[ImageAttachment]:
    attachments = getattr(message, "attachments", None) or []
    return [
        ImageAttachment.from_attachment(attachment)
        for attachment in attachments
        if is_image_attachment(attachment)
    ]


def log_image_attachments(
    source: str,
    message_id: str | None,
    sender_id: str | None,
    images: list[ImageAttachment],
) -> None:
    for index, image in enumerate(images, start=1):
        _log.info(
            "image attachment parsed: source=%s message_id=%s sender_id=%s "
            "index=%s attachment_id=%s content_type=%s filename=%s "
            "width=%s height=%s size=%s url=%s",
            source,
            message_id,
            sender_id,
            index,
            image.attachment_id,
            image.content_type,
            image.filename,
            image.width,
            image.height,
            image.size,
            image.url,
        )


def format_image_reply(images: list[ImageAttachment]) -> str:
    if len(images) == 1:
        image = images[0]
        size_text = f"{image.width}x{image.height}" if image.width and image.height else "未知尺寸"
        return f"收到 1 张图片，已记录日志。图片尺寸：{size_text}"

    return f"收到 {len(images)} 张图片，已记录日志。"


def _format_extracted_image_date(value: object) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    normalized = re.sub(r"[./]", "-", text)
    normalized = re.sub(r"年|月", "-", normalized).replace("日", "")
    normalized = normalized.strip()

    match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", normalized)
    if match:
        year, month, day = (int(part) for part in match.groups())
        try:
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            return None

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return None


def format_image_search_answer(content: str, answer: dict) -> str:
    from qqbot.handlers import format_search_date

    review = answer.get("user_review", "").replace("\n", " ").strip()
    return "\n".join(
        [
            f"【原始评价】 {content[:20]}{'...' if len(content) > 20 else ''}", "",
            f"【题目】 {review}",
            f"【时间】 {format_search_date(answer.get('timestamp'))}",
            (
                f"【答案】 {answer.get('answer', '')}  "
                f"(比例 {answer.get('ratio_1', '')}:{answer.get('ratio_2', '')})"
            ),
        ]
    )


def search_answer_from_image(image: ImageAttachment) -> str | None:
    if not image.url:
        _log.error("image search: 图片 URL 为空，attachment_id=%s", image.attachment_id)
        return "图片解析失败: 图片 URL 为空"

    try:
        from qqbot.ai import extract_img
        from qqbot.diaoxinxin import search_answers_from_image
        from qqbot.ocr import count_xiaomei_keywords

        keyword_count = count_xiaomei_keywords(image.url)
        _log.info(
            "image search: OCR 小美关键词计数完成，attachment_id=%s keyword_count=%d",
            image.attachment_id,
            keyword_count,
        )
        if keyword_count < 4:
            return None

        extracted = extract_img(image.url)
        if not extracted:
            _log.error("image search: 视觉模型未提取到评价，attachment_id=%s", image.attachment_id)
            return "图片解析失败: 未提取到评价内容"

        content = (extracted.get("content") or "").strip()
        if not content:
            _log.error("image search: 评价 content 为空，attachment_id=%s", image.attachment_id)
            return "图片解析失败: 评价内容为空"

        search_date = _format_extracted_image_date(extracted.get("date"))
        if not search_date:
            _log.error(
                "image search: 评价 date 无法解析，attachment_id=%s date=%s",
                image.attachment_id,
                extracted.get("date"),
            )
            return "图片解析失败: 评价日期为空或格式错误"

        keyword = content
        _log.info(
            "image search: 开始按图片评价搜题，attachment_id=%s content_length=%d date=%s",
            image.attachment_id,
            len(content),
            search_date,
        )
        results = search_answers_from_image(keyword, search_date)
        if not results:
            _log.error(
                "image search: 搜题结果为空，attachment_id=%s keyword_length=%d date=%s",
                image.attachment_id,
                len(keyword),
                search_date,
            )
            return f"原始评价: {content}\n搜题失败: 未找到答案"

        return format_image_search_answer(content, results[0])
    except Exception:
        _log.exception("image search: 图片解析搜题失败，attachment_id=%s", image.attachment_id)
        return "图片解析失败: 未知错误"
