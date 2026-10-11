/** One documented API operation, generated from the OpenAPI snapshot. */
export interface Operation {
  readonly method: 'GET' | 'PUT' | 'POST' | 'DELETE' | 'PATCH';
  readonly path: string;
  /** Whether repeating the operation has no additional effect, so it is safe to retry. */
  readonly idempotent: boolean;
  /** Whether the operation takes an `Idempotency-Key` header. */
  readonly idempotencyKey: boolean;
}
