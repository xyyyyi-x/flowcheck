"""执行器与外部设施之间的协议和领域异常。"""

from __future__ import annotations

from typing import Protocol

from app.domain.contracts import (
    RenderedRequest,
    ResponseData,
    RunOutcome,
    SafeStepResult,
)


class RunNoLongerActive(Exception):
    """栅栏失效：Worker 必须停止写入。"""


class TransportFailure(Exception):
    code = "NETWORK_ERROR"

    def __init__(self, message: str = "") -> None:
        super().__init__(message)
        self.message = message


class TargetNotAllowed(TransportFailure):
    code = "TARGET_NOT_ALLOWED"


class RequestTimeout(TransportFailure):
    code = "REQUEST_TIMEOUT"


class NetworkFailure(TransportFailure):
    code = "NETWORK_ERROR"


class ResponseTooLarge(TransportFailure):
    code = "RESPONSE_TOO_LARGE"


class RunBudgetExceeded(TransportFailure):
    code = "RUN_TIMEOUT"


class HttpTransport(Protocol):
    def send(
        self, request: RenderedRequest, timeout_s: int, remaining_s: float
    ) -> ResponseData: ...


class RunSink(Protocol):
    def start_step(self, position: int) -> None: ...

    def save_step(self, position: int, result: SafeStepResult) -> None: ...

    def finish(self, outcome: RunOutcome) -> None: ...
