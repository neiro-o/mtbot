from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
import re
from urllib.parse import parse_qs, urlparse


logger = logging.getLogger(__name__)

MAX_REPLY_LENGTH = 1800
XIAOMEI_URL_PATTERN = re.compile(r"https?://[^\s]+")
XIAOMEI_UPLOAD_PATHS = {
    "/xiaomei/vote/jury/api/r/rediectByScene",
    "/xiaomei/static/fsb-share-h5",
}
INVALID_XIAOMEI_UPLOAD_PARAMS = object()


@dataclass(frozen=True)
class MessageContext:
    source: str
    message_id: str
    sender_id: str


def truncate_reply(content: str) -> str:
    if len(content) <= MAX_REPLY_LENGTH:
        return content
    return content[: MAX_REPLY_LENGTH - 3] + "..."


def _mask_value(value: str, head: int = 6, tail: int = 4) -> str:
    if len(value) <= head + tail:
        return "***"
    return f"{value[:head]}...{value[-tail:]}"


def format_search_date(timestamp: object) -> str:
    if timestamp is None:
        return ""

    if isinstance(timestamp, str):
        stripped = timestamp.strip()
        if not stripped:
            return ""
        if stripped.isdigit():
            timestamp = int(stripped)
        else:
            try:
                return datetime.fromisoformat(stripped.replace("Z", "+00:00")).strftime(
                    "%Y-%m-%d"
                )
            except ValueError:
                logger.error("diaoxinxin search: 时间戳格式无法解析，timestamp=%s", stripped)
                return stripped

    if isinstance(timestamp, (int, float)):
        value = float(timestamp)
        if value > 10_000_000_000:
            value = value / 1000
        return datetime.fromtimestamp(value).strftime("%Y-%m-%d")

    logger.error("diaoxinxin search: 时间戳类型无法解析，timestamp_type=%s", type(timestamp))
    return str(timestamp)


def format_search_answer(answer: dict) -> str:
    return "\n".join(
        [
            f"【题目】 {answer.get('user_review', '')}",
            f"【时间】 {format_search_date(answer.get('timestamp'))}",
            (
                f"【答案】 {answer.get('answer', '')}  "
                f"(【比例】 {answer.get('ratio_1', '')}:{answer.get('ratio_2', '')})"
            ),
        ]
    )


def extract_xiaomei_upload_params(content: str) -> tuple[str, str] | None | object:
    for match in XIAOMEI_URL_PATTERN.finditer(content):
        url = match.group(0)
        try:
            parsed = urlparse(url)
        except Exception:
            logger.exception("xiaomei upload: URL 解析异常，url=%s", _mask_value(url))
            return INVALID_XIAOMEI_UPLOAD_PARAMS

        if parsed.netloc != "zqt.meituan.com" or parsed.path not in XIAOMEI_UPLOAD_PATHS:
            continue

        params = parse_qs(parsed.query)
        user_id = params.get("userId", [""])[0]
        task_id = params.get("encryptMockTaskNo", [""])[0]
        logger.info(
            "xiaomei upload: 匹配到分享链接，path=%s user_id=%s raw_task_id=%s",
            parsed.path,
            user_id,
            _mask_value(task_id),
        )

        task_id_padding_pos = task_id.find("==")
        if task_id_padding_pos != -1:
            task_id = task_id[: task_id_padding_pos + 2]

        if user_id and task_id.endswith("=="):
            logger.info(
                "xiaomei upload: 分享链接参数解析成功，user_id=%s task_id=%s",
                user_id,
                _mask_value(task_id),
            )
            return user_id, task_id

        logger.error(
            "xiaomei upload: 分享链接参数不符合规则，user_id_exists=%s "
            "task_id_ends_with_padding=%s raw_task_id=%s",
            bool(user_id),
            task_id.endswith("=="),
            _mask_value(params.get("encryptMockTaskNo", [""])[0]),
        )
        return INVALID_XIAOMEI_UPLOAD_PARAMS

    return None


def handle_text_message(content: str, context: MessageContext) -> str:
    text = content.strip()

    if text == "/ping":
        return "pong"

    if text == "/help":
        return "\n".join(
            [
                "可用命令：",
                "/ping - 检查机器人是否在线",
                "/help - 查看帮助",
                "/search {keyword} - 搜索题目答案",
            ]
        )

    if text == "/search" or text.startswith("/search "):
        keyword = text[len("/search") :].strip()
        if not keyword:
            return "搜题失败: 关键词不能为空"

        try:
            from qqbot.diaoxinxin import search_answers

            logger.info(
                "diaoxinxin search: 开始处理搜题命令，source=%s message_id=%s "
                "sender_id=%s keyword_length=%d",
                context.source,
                context.message_id,
                context.sender_id,
                len(keyword),
            )
            results = search_answers(keyword)
            if not results:
                logger.error("diaoxinxin search: 搜题结果为空，keyword_length=%d", len(keyword))
                return "搜题失败: 未找到答案"

            return format_search_answer(results[0])
        except Exception:
            logger.exception(
                "diaoxinxin search: 搜题未知错误，source=%s message_id=%s sender_id=%s",
                context.source,
                context.message_id,
                context.sender_id,
            )
            return "搜题失败: 未知错误"

    upload_params = extract_xiaomei_upload_params(text)
    if upload_params is INVALID_XIAOMEI_UPLOAD_PARAMS:
        return ""

    if upload_params is not None:
        try:
            from qqbot.diaoxinxin import upload_problem

            result = upload_problem(*upload_params)
            if result.get("code") == 0:
                return "上传题目成功"
            logger.error(
                "xiaomei upload: 上传题目失败，code=%s message=%s",
                result.get("code"),
                result.get("message"),
            )
            return f"上传题目失败: {result.get('message')}"
        except Exception:
            logger.exception(
                "xiaomei upload: 上传题目未知错误，source=%s message_id=%s sender_id=%s",
                context.source,
                context.message_id,
                context.sender_id,
            )
            return "上传题目失败: 未知错误"

    return f"收到你的消息：{text}"
