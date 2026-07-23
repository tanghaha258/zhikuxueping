"""
统一响应格式工具模块

遵循 API 规范中的统一响应格式：
```json
{
  "code": 0,
  "message": "success",
  "data": {},
  "trace_id": "req_20260521100000001"
}
```
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional


def _generate_trace_id() -> str:
    """生成请求追踪 ID，格式: req_YYYYMMDDHHMMSS_随机8位hex"""
    now = datetime.now(timezone.utc)
    return f"req_{now.strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"


def success_response(data: Any = None, message: str = "success") -> dict:
    """
    构造成功响应。

    Args:
        data: 响应数据（可为 None、dict、list、Pydantic model 等）。
        message: 提示信息。

    Returns:
        统一格式的成功响应字典。
    """
    # 将 Pydantic model 转为 dict
    if hasattr(data, "model_dump"):
        data = data.model_dump()
    elif hasattr(data, "dict"):
        data = data.dict()

    return {
        "code": 0,
        "message": message,
        "data": data,
        "trace_id": _generate_trace_id(),
    }


def error_response(
    code: int = 40001,
    message: str = "error",
    data: Any = None,
) -> dict:
    """
    构造错误响应。

    Args:
        code: 业务错误码（40000+）。
        message: 错误描述。
        data: 附加错误数据（通常为 None）。

    Returns:
        统一格式的错误响应字典。
    """
    return {
        "code": code,
        "message": message,
        "data": data,
        "trace_id": _generate_trace_id(),
    }
