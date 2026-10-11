import { readFileSync } from 'node:fs';
import { Ajv2020 } from 'ajv/dist/2020.js';
import formats from 'ajv-formats';
import { expect } from 'vitest';

// biome-ignore lint/suspicious/noExplicitAny: JSON Schema nodes are untyped.
type Schema = Record<string, any>;
interface OpenApiOperation {
  operationId: string;
  parameters?: { in: string; name: string; required?: boolean; schema?: Schema }[];
  requestBody?: { content: Record<string, { schema?: Schema }> };
  responses: Record<string, { content?: Record<string, { schema?: Schema }> }>;
}

interface Spec {
  paths: Record<string, Record<string, OpenApiOperation>>;
  components: Schema;
}
interface Entry {
  method: string;
  path: string;
  operation: OpenApiOperation;
}

export const spec: Spec = JSON.parse(
  readFileSync(new URL('../../openapi.json', import.meta.url), 'utf8'),
) as Spec;

export const operations: Map<string, Entry> = new Map();
for (const [path, item] of Object.entries(spec.paths)) {
  for (const method of ['get', 'put', 'post', 'delete', 'patch']) {
    const operation = item[method];
    if (operation)
      operations.set(operation.operationId, { method: method.toUpperCase(), path, operation });
  }
}

const ajv = new Ajv2020({ strict: false, allErrors: true });
// ajv-formats is CommonJS; under NodeNext its default export is the module object.
formats.default(ajv);
ajv.addSchema({ $id: 'openapi', components: spec.components });

function validate(schema: Schema, value: unknown, context: string): void {
  const check = ajv.compile({ $ref: 'openapi', ...rebase(schema) });
  expect(check(value), `${context}: ${ajv.errorsText(check.errors)}`).toBe(true);
}

function rebase(schema: Schema): Schema {
  return JSON.parse(JSON.stringify(schema).replaceAll('"#/components/', '"openapi#/components/'));
}

export async function assertRequestMatches(operationId: string, request: Request): Promise<void> {
  const entry = operations.get(operationId);
  if (!entry) throw new Error(`unknown operation ${operationId}`);
  expect(request.method).toBe(entry.method);
  const url = new URL(request.url);
  const expected = entry.path.split('/');
  const actual = url.pathname.split('/');
  expect(actual.length, url.pathname).toBe(expected.length);
  expected.forEach((segment, index) => {
    if (!segment.startsWith('{')) expect(actual[index], url.pathname).toBe(segment);
  });

  const parameters = entry.operation.parameters ?? [];
  const query = new Map(parameters.filter((p) => p.in === 'query').map((p) => [p.name, p]));
  for (const [name, value] of url.searchParams) {
    const parameter = query.get(name);
    expect(parameter, `${operationId} sends undocumented query parameter ${name}`).toBeDefined();
    const type = [parameter?.schema?.type].flat().find((item) => item !== 'null');
    const coerced =
      type === 'integer' ? Number(value) : type === 'boolean' ? value === 'true' : value;
    validate(parameter?.schema ?? {}, coerced, `${operationId} query ${name}`);
  }
  for (const [name, parameter] of query) {
    if (parameter.required)
      expect(url.searchParams.has(name), `${operationId} omits ${name}`).toBe(true);
  }
  const takesKey = parameters.some(
    (p) => p.in === 'header' && p.name.toLowerCase() === 'idempotency-key',
  );
  expect(request.headers.has('Idempotency-Key'), operationId).toBe(takesKey);

  const body = entry.operation.requestBody?.content ?? {};
  if (body['application/json']?.schema) {
    validate(body['application/json'].schema, await request.json(), `${operationId} body`);
  } else if (Object.keys(body).length > 0) {
    expect(request.headers.get('Content-Type'), operationId).toBeTruthy();
  }
}

export function successResponse(operationId: string): { status: number; schema?: Schema } {
  const entry = operations.get(operationId);
  if (!entry) throw new Error(`unknown operation ${operationId}`);
  const [status, response] = Object.entries(entry.operation.responses).find(([code]) =>
    code.startsWith('2'),
  ) as [string, { content?: Record<string, { schema?: Schema }> }];
  return { status: Number(status), schema: response.content?.['application/json']?.schema };
}

/** A schema-valid instance; `future` adds an unknown field and unknown enum values. */
// biome-ignore lint/suspicious/noExplicitAny: returns arbitrary schema-shaped JSON.
export function example(schema: Schema, future = false): any {
  if (schema.$ref) return example(spec.components.schemas[schema.$ref.split('/').pop()], future);
  for (const keyword of ['oneOf', 'anyOf']) {
    if (schema[keyword]) {
      return example(
        schema[keyword].find((branch: Schema) => branch.type !== 'null'),
        future,
      );
    }
  }
  if (schema.enum) return future ? 'value_added_later' : schema.enum[0];
  const type = [schema.type].flat().find((item) => item !== 'null');
  switch (type) {
    case 'object': {
      const value: Record<string, unknown> = Object.fromEntries(
        Object.entries(schema.properties ?? {}).map(([name, child]) => [
          name,
          example(child as Schema, future),
        ]),
      );
      if (future) value.field_added_later = { nested: true };
      return value;
    }
    case 'array':
      return [example(schema.items ?? {}, future)];
    case 'string':
      if (schema.format === 'date-time') return '2026-10-08T10:00:00Z';
      if (schema.pattern) return schema.pattern.includes('A-Z') ? 'USD' : '12.5';
      return 'text';
    case 'integer':
      return 1;
    case 'number':
      return 1.5;
    case 'boolean':
      return true;
    default:
      return {};
  }
}
