"""SDK 异常层级"""


class AgentError(Exception):
    """所有 SDK 异常的基类。"""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.body = body


class AuthError(AgentError):
    """401 - API Key 错误或缺失。"""


class RateLimitError(AgentError):
    """429 - 限流。"""


class ServerError(AgentError):
    """5xx - 服务端错误。"""


class TimeoutError(AgentError):
    """请求超时。"""


class StreamError(AgentError):
    """SSE 流解析失败 / 中途出错。"""
