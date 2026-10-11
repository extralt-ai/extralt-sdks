# Extralt Python SDK

The Python client for the [Extralt API](https://extralt.com/docs). It is typed, async-first with
an identical synchronous client, and retries safely on its own.

Requires Python 3.11+.

```bash
pip install extralt
```

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
import httpx

client = Extralt(
    api_key="...",  # defaults to EXTRALT_API_KEY
    timeout=60.0,  # seconds per request
    max_retries=2,
    http_client=httpx.Client(proxy="http://localhost:3128"),  # proxies, transports, hooks
)
```

Set `EXTRALT_LOG=info` to log each job's progress and every retry, or `debug` to add every
response. You can also configure the `extralt` logger yourself. API keys are never logged.

## Lists

`list()` returns a paginator. Iterating it fetches pages as needed:

```python
for run in client.extract.runs.list():
    ...

page = client.extract.runs.list(limit=50).first_page()
page.data, page.next_cursor

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

```python
with client.extract.captures.export(run_id=run.id, format="parquet") as export:
    export.write_to("captures.parquet")

imported = client.extract.imports.create("catalog.csv", country="US")  # streamed from disk
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

Connection errors, 408, 429 and 5xx responses are retried with exponential backoff, honouring
`Retry-After`, but only for operations that are safe to repeat. Creates and restarts send an
`Idempotency-Key` that every retry reuses, so a retried request never creates a second resource.
Pass `idempotency_key=` to retry the same logical request yourself.

## Forward compatibility

Responses are read without strict validation. Fields and enum values the API adds within v1 stay
available, as `model_extra` and as plain strings, instead of breaking older SDK versions.

## License

[MIT](https://github.com/extralt-ai/extralt-sdks/blob/main/python/LICENSE)
