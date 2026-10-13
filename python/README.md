# Extralt Python SDK

The Python client for the [Extralt API](https://extralt.com/docs). It is typed, has a synchronous
and an asynchronous client with the same methods, and retries safely on its own.

[Documentation](https://extralt.com/docs/using-the-api/sdks) ·
[API reference](https://api.extralt.com/docs) ·
[Changelog](https://github.com/extralt-ai/extralt-sdks/blob/main/python/CHANGELOG.md)

```bash
pip install extralt
```

It needs Python 3.11 or later and an
[API key](https://extralt.com/docs/guides/account-setup), which it reads from the
`EXTRALT_API_KEY` environment variable.

## Usage

```python
from extralt import Extralt

client = Extralt()  # reads EXTRALT_API_KEY

robot = client.extract.robots.create(url="https://www.example.com", country="US")
run = client.extract.runs.create(robot_id=robot.id, budget=100)

for capture in client.extract.captures.list(run_id=run.id):
    print(capture.title, capture.url)
```

Each call returns once its work is done: the Robot is built and the Run has finished before the
next line runs.

The asynchronous client has the same methods:

```python
from extralt import AsyncExtralt

async with AsyncExtralt() as client:
    run = await client.extract.runs.get(run_id)
    async for capture in client.extract.captures.list(run_id=run.id):
        print(capture.title)
```

## Configuration

```python
client = Extralt(
    api_key="...",  # defaults to EXTRALT_API_KEY
    timeout=60.0,  # seconds per request
    max_retries=2,
)
```

To go through a proxy, trust custom certificates or use your own transport, pass an
`httpx.Client` as `http_client` (an `httpx.AsyncClient` to the asynchronous client).

Set `EXTRALT_LOG=info` to log each job's progress and every retry, or `debug` to add every
response. You can also configure the `extralt` logger yourself. API keys are never logged.

## Lists

`list()` returns a paginator. Iterating it fetches pages as needed:

```python
for run in client.extract.runs.list():
    ...

page = client.extract.runs.list(limit=50).first_page()
print(len(page.data), page.next_cursor)

for page in client.extract.runs.list().pages():
    ...
```

## Jobs

Building a Robot, a Run, an Import and an Enrichment each take minutes. The call that starts one
polls with backoff and returns it finished, within one hour or the `timeout` you pass.

- A job that ends as `failed` raises `JobFailedError`, with the job in `.resource`. A job that
  was stopped is returned.
- When the time runs out, `WaitTimeoutError` carries the job in `.resource`. The job keeps
  running on Extralt, and `wait()` with its id resumes waiting.
- A Run needs a `budget`: the most Captures to produce, or `"unlimited"` to crawl until the store
  is done or credits run out.

```python
from extralt import JobFailedError, WaitTimeoutError

try:
    run = client.extract.runs.create(robot_id=robot.id, budget=100, timeout=600)
except JobFailedError as error:
    print(error.resource.status_reason)
except WaitTimeoutError as error:
    print(f"{error.resource.id} is still running")
```

To start a job without waiting for it, for example from a web request, pass `wait=False` and
wait for it elsewhere with its id:

```python
started = client.extract.runs.create(robot_id=robot.id, budget=100, wait=False)
finished = client.extract.runs.wait(started.id)
```

## Files

An export is a stream: write it to a file, or read it in chunks with `iter_bytes()`. An import
is streamed from disk.

```python
with client.extract.captures.export(run_id=run.id, format="parquet") as export:
    export.write_to("captures.parquet")

imported = client.extract.imports.create("catalog.csv", country="US")
```

## Explore

Explore reads the observed market: Stores, Products, Variants, Listings and Offers.

```python
import datetime as dt

for change in client.explore.changes.list(window="1w", event="price_changed"):
    print(change.title, change.before_price, change.after_price)

variant = client.explore.variants.get(variant_id)
for offer in client.explore.variants.offers(variant_id):
    print(offer.store_host, offer.price)

week_ago = dt.datetime.now(dt.UTC) - dt.timedelta(days=7)
movements = client.explore.analyses.price_movements(from_=week_ago, country="US", currency="USD")
analysis = movements.first_page()  # summary, coverage and freshness of the whole scope
for row in movements:  # every evidence row, across pages
    print(row.title, row.old_price, row.new_price)
```

Times are timezone-aware `datetime`s or RFC 3339 strings. `from` is spelled `from_`, since it is
a Python keyword. Prices, price differences and percentages are `decimal.Decimal`, so they compare
and add as numbers; a Capture's price stays the store's own text.

## SQL queries

Run your own read-only SQL over the organization's Captures, Items and Explore tables.

```python
model = client.query.model(entities=["current_offers"])  # tables, columns and rules
print([column.name for column in model.entities[0].columns])

result = client.query.run(
    "SELECT currency, count() AS offers FROM extralt.current_offers GROUP BY currency"
)
for row in result.rows:
    print(row)  # {"currency": "USD", "offers": "1250"}

with client.query.export("SELECT * FROM extralt.current_offers", format="parquet") as export:
    export.write_to("offers.parquet")
```

`run()` returns the rows that fit in one response and sets `truncated` when some were left out;
`export()` streams every row. 64-bit integers and decimals arrive as strings.

## Webhooks

A webhook endpoint receives the organization's events, such as a finished Run, whether the work
was started from the API, the dashboard or a schedule. Register one and keep its secret:

```python
endpoint = client.webhooks.create(
    url="https://hooks.example.com/extralt",
    event_types=["run.completed", "run.failed"],  # leave out for every event type
)
secret = endpoint.secret  # the API returns it only here
client.webhooks.test(endpoint.id)  # sends a webhook.test event
```

Deliveries are signed with [Standard Webhooks](https://www.standardwebhooks.com/).
`verify_webhook` checks the signature and the timestamp and returns the typed event. Pass it the
raw request body, before any JSON parsing: `request.get_data()` in Flask, `await request.body()`
in FastAPI.

```python
from extralt import WebhookVerificationError, verify_webhook
from extralt.webhooks import RunWebhookEvent


def handle(body: bytes, headers: dict[str, str]) -> int:
    try:
        event = verify_webhook(body, headers, secret)
    except WebhookVerificationError:
        return 400
    if isinstance(event, RunWebhookEvent) and event.type == "run.completed":
        print(event.data.id, event.data.status)  # event.data is the Run
    return 200
```

Answer with a 2xx status within 10 seconds; anything else is retried for about a day and a half.
Events arrive at least once and in no guaranteed order, so deduplicate on `event.id`. Event types
this SDK version does not know yet arrive as `UnknownWebhookEvent`.

## Errors and retries

API errors raise a subclass of `APIStatusError` with `status_code`, `code`, `message` and
`request_id`; include the request ID when contacting support.

| Status | Error |
| --- | --- |
| 400 | `BadRequestError` |
| 401 | `AuthenticationError` |
| 402 | `PaymentRequiredError` |
| 403 | `PermissionDeniedError` |
| 404 | `NotFoundError` |
| 409 | `ConflictError` |
| 413 | `PayloadTooLargeError` |
| 415 | `UnsupportedMediaTypeError` |
| 422 | `UnprocessableEntityError` |
| 429 | `RateLimitError` |
| 5xx | `InternalServerError` |

Network failures raise `APIConnectionError` (`APITimeoutError` for timeouts).

Connection errors, 408, 429 and 5xx responses are retried with exponential backoff, honoring
`Retry-After`, but only for operations that are safe to repeat. Creates and restarts send an
`Idempotency-Key` that every retry reuses, so a retried request never creates a second resource.
Pass `idempotency_key=` to retry the same logical request yourself.

## Forward compatibility

Responses are read without strict validation. Fields and enum values the API adds within v1 stay
available, as `model_extra` and as plain strings, instead of breaking older SDK versions.

## Versioning

The SDK follows semantic versioning. While it is `0.x`, a minor release can contain breaking
changes, which the
[changelog](https://github.com/extralt-ai/extralt-sdks/blob/main/python/CHANGELOG.md) lists.

## License

[MIT](https://github.com/extralt-ai/extralt-sdks/blob/main/python/LICENSE)
