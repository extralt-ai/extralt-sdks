from __future__ import annotations

from typing import Any

import httpx

__all__ = [
    "APIConnectionError",
    "APIStatusError",
    "APITimeoutError",
    "AuthenticationError",
    "BadRequestError",
    "ConflictError",
    "ExtraltError",
    "InternalServerError",
    "JobFailedError",
    "NotFoundError",
    "PayloadTooLargeError",
    "PaymentRequiredError",
    "PermissionDeniedError",
    "RateLimitError",
    "UnprocessableEntityError",
    "UnsupportedMediaTypeError",
    "WaitTimeoutError",
    "WebhookVerificationError",
]


class ExtraltError(Exception):
    """Base class for every error raised by the SDK."""


class APIConnectionError(ExtraltError):
    """The request did not produce an HTTP response."""

    def __init__(self, message: str = "Connection error", *, request: httpx.Request) -> None:
        super().__init__(message)
        self.request = request


class APITimeoutError(APIConnectionError):
    """The request timed out on the client."""

    def __init__(self, *, request: httpx.Request) -> None:
        super().__init__("Request timed out", request=request)


class APIStatusError(ExtraltError):
    """The API answered with an error status and its stable error envelope."""

    status_code: int
    code: str | None
    request_id: str | None
    details: dict[str, Any] | None

    def __init__(
        self,
        message: str,
        *,
        response: httpx.Response,
        code: str | None,
        request_id: str | None,
        details: dict[str, Any] | None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.response = response
        self.status_code = response.status_code
        self.code = code
        self.request_id = request_id
        self.details = details

    def __str__(self) -> str:
        parts = [f"{self.status_code}"]
        if self.code:
            parts.append(self.code)
        text = f"{' '.join(parts)}: {self.message}"
        if self.request_id:
            text += f" (request {self.request_id})"
        return text


class BadRequestError(APIStatusError):
    pass


class AuthenticationError(APIStatusError):
    pass


class PaymentRequiredError(APIStatusError):
    pass


class PermissionDeniedError(APIStatusError):
    pass


class NotFoundError(APIStatusError):
    pass


class ConflictError(APIStatusError):
    pass


class PayloadTooLargeError(APIStatusError):
    pass


class UnsupportedMediaTypeError(APIStatusError):
    pass


class UnprocessableEntityError(APIStatusError):
    pass


class RateLimitError(APIStatusError):
    pass


class InternalServerError(APIStatusError):
    pass


class JobFailedError(ExtraltError):
    """A Robot build, Run, Import or Enrichment ended as failed. `resource` is its final state."""

    def __init__(self, message: str, *, resource: Any) -> None:
        super().__init__(message)
        self.resource = resource


class WaitTimeoutError(ExtraltError):
    """A job did not finish within the call's `timeout`. It keeps running on Extralt.

    `resource` is its latest state; `wait()` with its id resumes waiting.
    """

    def __init__(self, message: str, *, resource: Any) -> None:
        super().__init__(message)
        self.resource = resource


class WebhookVerificationError(ExtraltError):
    """A webhook delivery's headers or signature do not check out. Answer it with a 400."""


STATUS_ERRORS: dict[int, type[APIStatusError]] = {
    400: BadRequestError,
    401: AuthenticationError,
    402: PaymentRequiredError,
    403: PermissionDeniedError,
    404: NotFoundError,
    409: ConflictError,
    413: PayloadTooLargeError,
    415: UnsupportedMediaTypeError,
    422: UnprocessableEntityError,
    429: RateLimitError,
}


def status_error(response: httpx.Response) -> APIStatusError:
    """Builds the typed error for an error response whose body has been read."""
    envelope: dict[str, Any] = {}
    try:
        body = response.json()
        if isinstance(body, dict) and isinstance(body.get("error"), dict):
            envelope = body["error"]
    except ValueError:
        pass
    message = envelope.get("message") or response.text or response.reason_phrase
    request_id = envelope.get("request_id") or response.headers.get("x-request-id")
    error_class = STATUS_ERRORS.get(response.status_code) or (
        InternalServerError if response.status_code >= 500 else APIStatusError
    )
    details = envelope.get("details")
    return error_class(
        str(message),
        response=response,
        code=envelope.get("code"),
        request_id=request_id,
        details=details if isinstance(details, dict) else None,
    )
