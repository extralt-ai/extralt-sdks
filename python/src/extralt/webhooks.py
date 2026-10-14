"""Verifies and reads the events Extralt POSTs to webhook endpoints.

Deliveries follow [Standard Webhooks](https://www.standardwebhooks.com/): the `webhook-id`,
`webhook-timestamp` and `webhook-signature` headers carry an HMAC-SHA256 signature, made with the
endpoint's `whsec_` secret, of the id, the timestamp and the raw body. Events are delivered at
least once and in no guaranteed order: deduplicate on `event.id`, and read the resource from the
API when you need its current state.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import time
from collections.abc import Mapping
from typing import Any, Literal, get_args

from pydantic import AwareDatetime, BaseModel, ConfigDict

from ._construct import construct
from ._exceptions import WebhookVerificationError
from .types import Enrichment, Import, Robot, Run

__all__ = [
    "EnrichmentWebhookEvent",
    "ImportWebhookEvent",
    "RobotWebhookEvent",
    "RunWebhookEvent",
    "TestWebhookEvent",
    "UnknownWebhookEvent",
    "WebhookEvent",
    "WebhookTestData",
    "WebhookVerificationError",
    "verify_webhook",
]

DEFAULT_TOLERANCE = 300
"""Seconds a delivery's timestamp may differ from the clock before it is refused as a replay."""


class _Event(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    """Stable across retries of the same event to the same endpoint: deduplicate on it."""
    created_at: AwareDatetime


class RobotWebhookEvent(_Event):
    type: Literal["robot.completed", "robot.failed"]
    data: Robot


class RunWebhookEvent(_Event):
    type: Literal["run.completed", "run.stopped", "run.failed", "run.enrichment_skipped"]
    data: Run


class EnrichmentWebhookEvent(_Event):
    """`enrichment.changes` summarizes what the Enrichment found in `data.changes`: price
    decreases and increases, stock changes, Listings added and removed, and new lows."""

    type: Literal[
        "enrichment.completed", "enrichment.stopped", "enrichment.failed", "enrichment.changes"
    ]
    data: Enrichment


class ImportWebhookEvent(_Event):
    type: Literal["import.completed", "import.failed"]
    data: Import


class WebhookTestData(BaseModel):
    model_config = ConfigDict(extra="allow")
    webhook_id: str
    message: str


class TestWebhookEvent(_Event):
    """Sent by `webhooks.test()` or from the dashboard, whatever event types the endpoint wants."""

    __test__ = False  # not a pytest test class
    type: Literal["webhook.test"]
    data: WebhookTestData


class UnknownWebhookEvent(_Event):
    """An event type this SDK version does not know yet. New types are added within v1."""

    type: str
    data: Any = None


WebhookEvent = (
    RobotWebhookEvent
    | RunWebhookEvent
    | EnrichmentWebhookEvent
    | ImportWebhookEvent
    | TestWebhookEvent
    | UnknownWebhookEvent
)

_EVENTS: dict[str, type[_Event]] = {
    event_type: event_class
    for event_class in (
        RobotWebhookEvent,
        RunWebhookEvent,
        EnrichmentWebhookEvent,
        ImportWebhookEvent,
        TestWebhookEvent,
    )
    for event_type in get_args(event_class.model_fields["type"].annotation)
}


def verify_webhook(
    payload: str | bytes,
    headers: Mapping[str, str],
    secret: str,
    *,
    tolerance: float = DEFAULT_TOLERANCE,
) -> WebhookEvent:
    """Checks a delivery's signature and returns its event.

    Pass the raw request body exactly as received, before any JSON parsing, the request's headers
    and the endpoint's `whsec_` secret. Raises `WebhookVerificationError` when a header is
    missing, the signature does not match, or the timestamp is more than `tolerance` seconds from
    now. Narrow the event with `isinstance`, for example `RunWebhookEvent`, whose `data` is a Run.
    """
    if not isinstance(payload, (str, bytes)):
        raise TypeError("payload must be the raw request body as str or bytes, not parsed JSON")
    body = payload.encode() if isinstance(payload, str) else payload
    lowered = {name.lower(): value for name, value in headers.items()}
    message_id = lowered.get("webhook-id")
    timestamp = lowered.get("webhook-timestamp")
    signatures = lowered.get("webhook-signature")
    if not message_id or not timestamp or not signatures:
        raise WebhookVerificationError(
            "The webhook-id, webhook-timestamp and webhook-signature headers are required."
        )
    try:
        sent_at = int(timestamp)
    except ValueError:
        raise WebhookVerificationError("The webhook-timestamp header is not a number.") from None
    if abs(time.time() - sent_at) > tolerance:
        raise WebhookVerificationError("The webhook timestamp is outside the tolerance.")
    digest = hmac.new(
        _secret_key(secret), f"{message_id}.{timestamp}.".encode() + body, hashlib.sha256
    ).digest()
    expected = base64.b64encode(digest).decode()
    if not any(
        version == "v1" and hmac.compare_digest(value, expected)
        for version, _, value in (signature.partition(",") for signature in signatures.split())
    ):
        raise WebhookVerificationError("No webhook signature matches the payload.")
    try:
        event = json.loads(body)
    except ValueError:
        raise WebhookVerificationError("The webhook payload is not JSON.") from None
    if not isinstance(event, dict):
        raise WebhookVerificationError("The webhook payload is not an event.")
    return construct(_EVENTS.get(event.get("type"), UnknownWebhookEvent), event)


def _secret_key(secret: str) -> bytes:
    try:
        return base64.b64decode(secret.removeprefix("whsec_"), validate=True)
    except binascii.Error:
        raise ValueError("secret must be the endpoint's whsec_ signing secret") from None
