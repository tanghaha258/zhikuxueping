"""统一 AI 异常码与异常类型。

AI 网关及依赖 AI 的业务模块（评卷、备课、出卷等）统一使用这些错误码，
以便调用方区分失败原因，并在 AI 不可用时返回明确的不可用状态，
而不是伪造分数、教案或虚假成功结果。
"""
from enum import Enum


class AiErrorCode(str, Enum):
    """AI 调用失败的原因码。"""

    PROVIDER_UNAVAILABLE = "provider_unavailable"
    TIMEOUT = "timeout"
    INVALID_OUTPUT = "invalid_output"
    SAFETY_BLOCKED = "safety_blocked"


class AiUnavailableError(Exception):
    """AI 无法产出可信结果时抛出。

    携带稳定的 ``code``（AiErrorCode），供路由 / 服务层映射为明确的不可用状态，
    而不是写入模拟分数或正式教案。
    """

    def __init__(self, code: AiErrorCode, message: str = ""):
        self.code = code
        self.message = message or code.value
        super().__init__(self.message)


def unavailable_result(code: AiErrorCode, message: str = "") -> dict:
    """构造统一的“AI 不可用”返回结构，供函数式调用直接返回。

    包含 ``evaluation_record_id=None`` 以保持与成功结果一致的契约，
    便于调用方用 ``result.get("evaluation_record_id")`` 判断是否产出了可采纳结果。
    """
    return {
        "status": "unavailable",
        "error_code": code.value,
        "message": message or code.value,
        "evaluation_record_id": None,
    }
