"""
diaoxinxin.com 后台模块：鉴权 + 题目搜索。

- token 缓存在模块级变量，避免重复登录。
- 遇到 401/403 或 token 失效时自动刷新，最多重试 MAX_RETRIES 次。
"""

import os
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://diaoxinxin.com/api"
MAX_RETRIES = 3
SEARCH_LIMIT = 5

_token: Optional[str] = None


def _mask_value(value: str, head: int = 6, tail: int = 4) -> str:
    if len(value) <= head + tail:
        return "***"
    return f"{value[:head]}...{value[-tail:]}"


def _get_credentials() -> tuple[str, str]:
    username = os.environ.get("DIAOXINXIN_USERNAME", "")
    password = os.environ.get("DIAOXINXIN_PASSWORD", "")
    if not username or not password:
        logger.error("diaoxinxin: 登录凭据未配置")
        raise RuntimeError(
            "DIAOXINXIN_USERNAME / DIAOXINXIN_PASSWORD 未在环境变量中配置"
        )
    return username, password


def _login() -> str:
    """向登录接口获取 Bearer Token 并缓存。"""
    global _token
    username, password = _get_credentials()
    logger.info("diaoxinxin: 开始登录，username=%s", username)
    try:
        resp = httpx.post(
            f"{BASE_URL}/login",
            json={"username": username, "password": password},
            timeout=10,
        )
        resp.raise_for_status()
    except Exception:
        logger.exception("diaoxinxin: 登录请求失败")
        raise

    data = resp.json()
    token = data["data"]["token"]
    _token = token
    logger.info("diaoxinxin: 登录成功，已刷新 token")
    return token


def _ensure_token() -> str:
    global _token
    if _token is None:
        logger.info("diaoxinxin: token 不存在，准备登录")
        _token = _login()
    return _token


def search_answers(keyword: str) -> list[dict]:
    """
    搜索题目答案。

    :param keyword: 搜索关键词
    :return: data.results 列表（dict list）
    :raises RuntimeError: 超出最大重试次数仍失败
    """
    global _token
    _ensure_token()
    logger.info("diaoxinxin: 开始搜索题目，keyword_length=%d", len(keyword))

    for attempt in range(1, MAX_RETRIES + 1):
        headers = {"Authorization": f"Bearer {_token}"}
        logger.info(
            "diaoxinxin: 搜索题目请求，第 %d/%d 次，limit=%d",
            attempt,
            MAX_RETRIES,
            SEARCH_LIMIT,
        )
        try:
            resp = httpx.get(
                f"{BASE_URL}/problem/search",
                params={"keyword": keyword, "limit": SEARCH_LIMIT},
                headers=headers,
                timeout=10,
            )
        except Exception:
            logger.exception("diaoxinxin: 搜索题目请求异常，第 %d/%d 次", attempt, MAX_RETRIES)
            raise

        if resp.status_code in (401, 403):
            logger.warning(
                "diaoxinxin: token 失效（%s），第 %d 次重新登录",
                resp.status_code,
                attempt,
            )
            if attempt < MAX_RETRIES:
                _token = _login()
                continue
            else:
                raise RuntimeError(
                    f"diaoxinxin: 超出最大重试次数（{MAX_RETRIES}），token 仍然无效"
                )

        try:
            resp.raise_for_status()
            results = resp.json()["data"]["results"]
        except Exception:
            logger.exception(
                "diaoxinxin: 搜索题目响应处理失败，status_code=%s",
                resp.status_code,
            )
            raise

        logger.info("diaoxinxin: 搜索题目成功，results_count=%d", len(results))
        return results

    # 不应走到这里
    raise RuntimeError("diaoxinxin: search_answers 意外退出重试循环")


def search_answers_from_image(keyword: str, date: str) -> list[dict]:
    """
    按图片解析结果搜索题目答案。

    :param keyword: 图片解析出的评价内容
    :param date: 图片解析出的评价日期，格式为 YYYY-mm-dd
    :return: data.results 列表（dict list）
    :raises RuntimeError: 超出最大重试次数仍失败
    """
    global _token
    _ensure_token()
    logger.info(
        "diaoxinxin: 开始按图片解析结果搜索题目，keyword_length=%d date=%s",
        len(keyword),
        date,
    )

    for attempt in range(1, MAX_RETRIES + 1):
        headers = {"Authorization": f"Bearer {_token}"}
        logger.info(
            "diaoxinxin: 图片搜题请求，第 %d/%d 次，date=%s",
            attempt,
            MAX_RETRIES,
            date,
        )
        try:
            resp = httpx.get(
                f"{BASE_URL}/bot/search",
                params={"keyword": keyword, "date": date},
                headers=headers,
                timeout=10,
            )
        except Exception:
            logger.exception("diaoxinxin: 图片搜题请求异常，第 %d/%d 次", attempt, MAX_RETRIES)
            raise

        if resp.status_code in (401, 403):
            logger.warning(
                "diaoxinxin: token 失效（%s），第 %d 次重新登录",
                resp.status_code,
                attempt,
            )
            if attempt < MAX_RETRIES:
                _token = _login()
                continue
            else:
                raise RuntimeError(
                    f"diaoxinxin: 超出最大重试次数（{MAX_RETRIES}），token 仍然无效"
                )

        try:
            resp.raise_for_status()
            results = resp.json()["data"]["results"]
        except Exception:
            logger.exception(
                "diaoxinxin: 图片搜题响应处理失败，status_code=%s",
                resp.status_code,
            )
            raise

        logger.info("diaoxinxin: 图片搜题成功，results_count=%d", len(results))
        return results

    raise RuntimeError("diaoxinxin: search_answers_from_image 意外退出重试循环")


def upload_problem(user_id: str, task_id: str) -> dict:
    """
    上传题目。

    :param user_id: 用户 ID
    :param task_id: 任务 ID
    :return: {"code": ..., "message": ...}
    :raises RuntimeError: 超出最大重试次数仍失败
    """
    global _token
    _ensure_token()
    logger.info(
        "diaoxinxin: 开始上传题目，user_id=%s task_id=%s",
        user_id,
        _mask_value(task_id),
    )

    for attempt in range(1, MAX_RETRIES + 1):
        headers = {"Authorization": f"Bearer {_token}"}
        logger.info(
            "diaoxinxin: 上传题目请求，第 %d/%d 次，user_id=%s task_id=%s",
            attempt,
            MAX_RETRIES,
            user_id,
            _mask_value(task_id),
        )
        try:
            resp = httpx.post(
                f"{BASE_URL}/problem/upload",
                json={"userId": user_id, "taskId": task_id},
                headers=headers,
                timeout=10,
            )
        except Exception:
            logger.exception(
                "diaoxinxin: 上传题目请求异常，第 %d/%d 次，user_id=%s task_id=%s",
                attempt,
                MAX_RETRIES,
                user_id,
                _mask_value(task_id),
            )
            raise

        if resp.status_code in (401, 403):
            logger.warning(
                "diaoxinxin: token 失效（%s），第 %d 次重新登录",
                resp.status_code,
                attempt,
            )
            if attempt < MAX_RETRIES:
                _token = _login()
                continue
            else:
                raise RuntimeError(
                    f"diaoxinxin: 超出最大重试次数（{MAX_RETRIES}），token 仍然无效"
                )

        try:
            resp.raise_for_status()
            body = resp.json()
            result = {"code": body["code"], "message": body["message"]}
        except Exception:
            logger.exception(
                "diaoxinxin: 上传题目响应处理失败，status_code=%s user_id=%s task_id=%s",
                resp.status_code,
                user_id,
                _mask_value(task_id),
            )
            raise

        logger.info(
            "diaoxinxin: 上传题目完成，code=%s message=%s user_id=%s task_id=%s",
            result["code"],
            result["message"],
            user_id,
            _mask_value(task_id),
        )
        return result

    raise RuntimeError("diaoxinxin: upload_problem 意外退出重试循环")
