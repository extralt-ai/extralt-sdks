# Extralt TypeScript SDK

The TypeScript client for the [Extralt API](https://extralt.com/docs).

```bash
npm install extralt
```

```ts
import { Extralt } from 'extralt';

const client = new Extralt(); // reads EXTRALT_API_KEY where the runtime exposes it

const robot = await client.extract.robots.create({ url: 'https://www.example.com', country: 'US' });
const run = await client.extract.runs.create({ robot_id: robot.id, budget: 100 });

for await (const capture of client.extract.captures.list({ run_id: run.id })) {
  console.log(capture.title, capture.url);
}
```

Each call resolves once its work is done: the Robot is built and the Run has finished before the
next line runs.

## Configuration

```ts
const client = new Extralt({
  apiKey: 'your-api-key', // defaults to the EXTRALT_API_KEY environment variable
  timeout: 60_000, // milliseconds, up to response headers
  maxRetries: 2,
  fetch: customFetch, // proxies, tracing, tests
});
```

Every method also takes `{ signal, timeout }`, and creates take `idempotencyKey`.

Set `logLevel: 'info'` or `EXTRALT_LOG=info` to log each job's progress and every retry, or
`debug` to add every response. Pass `logger` to send the lines somewhere other than `console`.
API keys are never logged.

## Lists

`list()` returns a paginator. Iterating it fetches pages as needed:

```ts
for await (const run of client.extract.runs.list()) {
}

const page = await client.extract.runs.list({ limit: 50 }).firstPage();

for await (const page of client.extract.runs.list().pages()) {
}
```

## Jobs

Building a Robot, a Run, an Import and an Enrichment each take minutes. The call that starts one
polls with backoff and resolves with it finished, within one hour or the `timeout` you pass.

- A job that ends as `failed` rejects with `JobFailedError`, with the job in `.resource`. A job
  that was stopped is returned.
- When the time runs out, `WaitTimeoutError` carries the job in `.resource`. The job keeps
  running on Extralt, and `wait()` with its id resumes waiting.
- A Run needs a `budget`: the most Captures to produce, or `'unlimited'` to crawl until the store
  is done or credits run out.

```ts
import { JobFailedError, WaitTimeoutError } from 'extralt';

try {
  await client.extract.runs.create({ robot_id: run.robot_id, budget: 100 }, { timeout: 600_000 });
} catch (error) {
  if (error instanceof JobFailedError) console.error(error.resource.status_reason);
  else if (error instanceof WaitTimeoutError) console.error(`${error.resource.id} is still running`);
  else throw error;
}
```

To start a job without waiting for it, for example from a web request, pass `wait: false` and
wait for it elsewhere with its id:

```ts
const started = await client.extract.runs.create(
  { robot_id: run.robot_id, budget: 100 },
  { wait: false },
);
const finished = await client.extract.runs.wait(started.id);
```

## Files

```ts
import { createWriteStream, openAsBlob } from 'node:fs';
import { Readable } from 'node:stream';
import { pipeline } from 'node:stream/promises';

const download = await client.extract.captures.export({ run_id: run.id, format: 'parquet' });
await pipeline(Readable.fromWeb(download.body), createWriteStream('captures.parquet'));

const catalog = await openAsBlob('catalog.csv', { type: 'text/csv' }); // streamed from disk
const imported = await client.extract.imports.create(catalog, { country: 'US' });
```

## Explore

Explore reads the observed market: Stores, Products, Variants, Listings and Offers.

```ts
for await (const change of client.explore.changes.list({ window: '1w', event: 'price_changed' })) {
  console.log(change.title, change.before_price, change.after_price);
}

const variant = await client.explore.variants.get(variantId);
for await (const offer of client.explore.variants.offers(variantId)) {
  console.log(offer.store_host, offer.price);
}

const weekAgo = new Date(Date.now() - 7 * 86_400_000).toISOString();
const movements = client.explore.analyses.priceMovements({
  from: weekAgo,
  country: 'US',
  currency: 'USD',
});
const analysis = await movements.firstPage(); // summary, coverage and freshness of the whole scope
for await (const row of movements) {
  // every evidence row, across pages
}
```

Times are RFC 3339 strings, such as `new Date().toISOString()`. Prices, price differences and
percentages are decimal strings, which keep their exact value: convert one with `Number()` before
comparing or adding.

## SQL queries

Run your own read-only SQL over the organization's Captures, Items and Explore tables.

```ts
const model = await client.query.model({ entities: ['current_offers'] }); // tables, columns, rules
console.log(model.entities[0]?.columns.map((column) => column.name));

const result = await client.query.run({
  sql: 'SELECT currency, count() AS offers FROM extralt.current_offers GROUP BY currency',
});
for (const row of result.rows) {
  console.log(row); // { currency: 'USD', offers: '1250' }
}

const download = await client.query.export({
  sql: 'SELECT * FROM extralt.current_offers',
  format: 'parquet',
});
await download.arrayBuffer(); // or stream download.body to disk
```

`run()` returns the rows that fit in one response and sets `truncated` when some were left out;
`export()` streams every row. 64-bit integers and decimals arrive as strings.

## Errors and retries

API errors reject with a subclass of `APIStatusError` carrying `status`, `code`, `message` and
`requestId`: `BadRequestError` (400), `AuthenticationError` (401), `PaymentRequiredError` (402),
`PermissionDeniedError` (403), `NotFoundError` (404), `ConflictError` (409),
`PayloadTooLargeError` (413), `UnsupportedMediaTypeError` (415), `UnprocessableEntityError` (422),
`RateLimitError` (429) and `InternalServerError` (5xx). Network failures reject with
`APIConnectionError` (`APITimeoutError` for timeouts).

Network errors, 408, 429 and 5xx responses are retried with exponential backoff, honouring
`Retry-After`, but only for operations that are safe to repeat. Creates and restarts send an
`Idempotency-Key` that every retry reuses, so a retried request never creates a second resource.

## Types

Every request and response type is exported by name, such as `Run`, `RunCreateParams` and
`Schedule`. Responses are not validated at runtime, so fields and enum values the API adds within
v1 pass through to older SDK versions.

## License

[MIT](https://github.com/extralt-ai/extralt-sdks/blob/main/typescript/LICENSE)
