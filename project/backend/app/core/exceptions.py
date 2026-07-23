"""
自定义异常模块

定义业务异常，配合全局异常处理器输出统一格式的错误响应。
"""


class AppException(Exception):
    """
    应用业务异常，携带业务错误码和 HTTP 状态码。

    用法示例：
        raise AppException(code=40001, message="invalid credentials", status_code=401)
    """

    def __init__(
        self,
        code: int = 40001,
        message: str = "error",
        status_code: int = 400,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)
