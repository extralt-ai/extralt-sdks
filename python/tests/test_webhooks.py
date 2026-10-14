from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import json
import time

import pytest

from extralt import WebhookVerificationError, verify_webhook
from extralt.types import Run
from extralt.webhooks import RunWebhookEvent, TestWebhookEvent, UnknownWebhookEvent

from . import spec

SECRET = "whsec_MfKQ9r8GKYqrTwjUPD8ILPZIo2LaLaSw"


def signed(body: str, *, secret: str = SECRET, sent_at: int | None = None) -> dict[str, str]:
    """Headers as Extralt sends them, signed like the delivery action in Convex."""
    timestamp = str(int(time.time()) if sent_at is None else sent_at)
    key = base64.b64decode(secret.removeprefix("whsec_"))
    digest = hmac.new(key, f"evt_1.{timestamp}.{body}".encode(), hashlib.sha256).digest()
    return {
        "webhook-id": "evt_1",
        "webhook-timestamp": timestamp,
        "webhook-signature": f"v1,{base64.b64encode(digest).decode()}",
    }


def event(type_: str, data: object) -> str:
    return json.dumps(
        {"id": "evt_1", "type": type_, "created_at": "2026-10-12T10:40:50Z", "data": data}
    )


def run_data() -> dict[str, object]:
    _, schema = spec.success_response("get_run")
    assert schema is not None
    return spec.example(schema)


def test_matches_the_standard_webhooks_reference_signature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(time, "time", lambda: 1614265330)
    headers = {
        "webhook-id": "msg_p5jXN8AQM9LWM0D4loKWxJek",
        "webhook-timestamp": "1614265330",
        "webhook-signature": "v1,g0hM9SsE+OTPJTGt/tmIKtSyZlE3uFJELVlNIOLJ1OE=",
    }
    verified = verify_webhook('{"test": 2432232314}', headers, SECRET)
    assert isinstance(verified, UnknownWebhookEvent)
    with pytest.raises(WebhookVerificationError, match="No webhook signature"):
        verify_webhook('{"test": 2432232315}', headers, SECRET)


def test_returns_a_typed_run_event() -> None:
    body = event("run.completed", run_data())
    verified = verify_webhook(body.encode(), signed(body), SECRET)
    assert isinstance(verified, RunWebhookEvent)
    assert verified.type == "run.completed"
    assert verified.created_at == dt.datetime(2026, 10, 12, 10, 40, 50, tzinfo=dt.UTC)
    assert isinstance(verified.data, Run)
    assert verified.data.id == run_data()["id"]


def test_returns_the_test_event() -> None:
    body = event("webhook.test", {"webhook_id": "webhook_1", "message": "Hello"})
    verified = verify_webhook(body, signed(body), SECRET)
    assert isinstance(verified, TestWebhookEvent)
    assert verified.data.webhook_id == "webhook_1"


def test_keeps_event_types_added_later_readable() -> None:
    body = event("enrichment.changes", {"enrichment_id": "enrichment_1", "new": 3})
    verified = verify_webhook(body, signed(body), SECRET)
    assert isinstance(verified, UnknownWebhookEvent)
    assert verified.type == "enrichment.changes"
    assert verified.data == {"enrichment_id": "enrichment_1", "new": 3}


def test_reads_headers_in_any_case_and_any_matching_signature() -> None:
    body = event("webhook.test", {"webhook_id": "w", "message": "m"})
    headers = {name.title(): value for name, value in signed(body).items()}
    headers["Webhook-Signature"] = "v1,bm90IGl0 " + headers["Webhook-Signature"]
    assert isinstance(verify_webhook(body, headers, SECRET), TestWebhookEvent)


def test_refuses_a_body_changed_after_signing() -> None:
    body = event("webhook.test", {"webhook_id": "w", "message": "m"})
    with pytest.raises(WebhookVerificationError, match="No webhook signature"):
        verify_webhook(body.replace('"m"', '"x"'), signed(body), SECRET)


def test_refuses_another_endpoints_secret() -> None:
    body = event("webhook.test", {"webhook_id": "w", "message": "m"})
    other = "whsec_" + base64.b64encode(b"another endpoint's secret!!!!!!!").decode()
    with pytest.raises(WebhookVerificationError):
        verify_webhook(body, signed(body, secret=other), SECRET)


@pytest.mark.parametrize("age", [-301, 301])
def test_refuses_a_timestamp_outside_the_tolerance(age: int) -> None:
    body = event("webhook.test", {"webhook_id": "w", "message": "m"})
    headers = signed(body, sent_at=int(time.time()) - age)
    with pytest.raises(WebhookVerificationError, match="tolerance"):
        verify_webhook(body, headers, SECRET)
    assert verify_webhook(body, headers, SECRET, tolerance=600)


@pytest.mark.parametrize("header", ["webhook-id", "webhook-timestamp", "webhook-signature"])
def test_refuses_a_delivery_without_its_headers(header: str) -> None:
    body = event("webhook.test", {"webhook_id": "w", "message": "m"})
    headers = signed(body)
    del headers[header]
    with pytest.raises(WebhookVerificationError, match="required"):
        verify_webhook(body, headers, SECRET)


def test_refuses_parsed_json_and_a_malformed_secret() -> None:
    body = event("webhook.test", {"webhook_id": "w", "message": "m"})
    with pytest.raises(TypeError, match="raw request body"):
        verify_webhook(json.loads(body), signed(body), SECRET)
    with pytest.raises(ValueError, match="whsec_"):
        verify_webhook(body, signed(body), "whsec_not base64!")
