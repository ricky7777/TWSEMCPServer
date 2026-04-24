"""Decorators for error handling and common patterns."""

import json
import re
from functools import wraps
from typing import Callable, TypeVar, ParamSpec
import logging

from .constants import MSG_QUERY_FAILED, MSG_NO_DATA

logger = logging.getLogger(__name__)

P = ParamSpec('P')
R = TypeVar('R')


def _get_last_upstream_url() -> str | None:
    try:
        from .api_client import TWSEAPIClient
        url = TWSEAPIClient._last_upstream_url
        return url if url else None
    except Exception:
        return None


def _infer_code_hint(code: str | None) -> str:
    if not code:
        return "unknown"
    if re.fullmatch(r'0\d{3}', code):
        return "etf"
    if re.fullmatch(r'[1-9]\d{3}', code):
        return "listed_company"
    if re.fullmatch(r'\d{4}[RTrt]', code):
        return "reits"
    return "unknown"


def _build_response(
    status: str,
    code: str | None,
    data_type: str,
    data,
    error: str | None = None,
) -> str:
    hint = _infer_code_hint(code)
    upstream_url = _get_last_upstream_url()

    if status == "ok":
        message = ""
    elif status == "no_data":
        if hint == "etf":
            message = "查無資料，若為 ETF（代號前綴 00）請改用 get_fund_basic_info"
        elif code:
            message = f"查無「{code}」的{data_type}資料"
        else:
            message = f"查無{data_type}資料"
    else:
        message = error or "發生未知錯誤"

    return json.dumps(
        {
            "status": status,
            "code_hint": hint,
            "message": message,
            "upstream_url": upstream_url,
            "data": data,
        },
        ensure_ascii=False,
    )


def handle_api_errors(data_type: str = "", use_code_param: bool = False):
    """
    Decorator to handle common API errors and logging.

    All return paths emit a structured JSON string with keys:
        status, code_hint, message, upstream_url, data

    Args:
        data_type: Type of data being queried (e.g., "券商資料")
        use_code_param: If True, extracts the 'code' parameter for hint inference
    """
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            code = None
            if use_code_param:
                code = kwargs.get('code')
                if code is None and len(args) > 0:
                    code = args[0]

            try:
                result = func(*args, **kwargs)
            except Exception as e:
                error_context = f" for code {code}" if code else ""
                logger.error(f"Error in {func.__name__}{error_context}: {e}", exc_info=True)
                return _build_response("error", code, data_type, None, str(e))

            if result is None or result == "":
                return _build_response("no_data", code, data_type, None)

            return _build_response("ok", code, data_type, result)

        return wrapper
    return decorator


def handle_empty_response(data_type: str):
    """
    Decorator to handle empty API responses.

    All return paths emit a structured JSON string with keys:
        status, code_hint, message, upstream_url, data

    Args:
        data_type: Type of data for the error message (e.g., "券商資料")
    """
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            code = kwargs.get('code')
            if code is None and len(args) > 0 and isinstance(args[0], str):
                code = args[0]

            result = func(*args, **kwargs)

            if result is None or result == "":
                return _build_response("no_data", code, data_type, None)

            return _build_response("ok", code, data_type, result)

        return wrapper
    return decorator
