from __future__ import annotations

from collections.abc import Sequence

from ..._base import json_body
from ..._operation import operation
from ...types import Webhook, WebhookEventType, WebhookList, WebhookTestResult, WebhookWithSecret
from .._resource import AsyncResource


class AsyncWebhooks(AsyncResource):
    """HTTPS endpoints that receive the organization's events. Verify each delivery with
    `verify_webhook`."""

    @operation("create_webhook")
    async def create(
        self,
        *,
        url: str,
        event_types: Sequence[WebhookEventType] | None = None,
        description: str | None = None,
        idempotency_key: str | None = None,
        timeout: float | None = None,
    ) -> WebhookWithSecret:
        """Registers an HTTPS endpoint and returns it with its signing `secret`.

        Leave out `event_types` to receive every event type, including ones added later. The API
        returns the secret only here; keep it to verify deliveries.
        """
        return await self._call(
            "create_webhook",
            WebhookWithSecret,
            json=json_body({"url": url, "event_types": event_types, "description": description}),
            idempotency_key=idempotency_key,
            timeout=timeout,
        )

    @operation("list_webhooks")
    async def list(self, *, timeout: float | None = None) -> WebhookList:
        return await self._call("list_webhooks", WebhookList, timeout=timeout)

    @operation("get_webhook")
    async def get(self, id: str, *, timeout: float | None = None) -> Webhook:
        return await self._call("get_webhook", Webhook, path_params={"id": id}, timeout=timeout)

    @operation("delete_webhook")
    async def delete(self, id: str, *, timeout: float | None = None) -> None:
        """Deletes the endpoint and its delivery history."""
        await self._http.request("delete_webhook", path_params={"id": id}, timeout=timeout)

    @operation("test_webhook")
    async def test(self, id: str, *, timeout: float | None = None) -> WebhookTestResult:
        """Sends a `webhook.test` event to the endpoint once, without retries."""
        return await self._call(
            "test_webhook", WebhookTestResult, path_params={"id": id}, timeout=timeout
        )
