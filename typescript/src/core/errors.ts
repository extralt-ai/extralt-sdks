/** Base class for every error raised by the SDK. */
export class ExtraltError extends Error {
  override name = 'ExtraltError';
}

/** The request did not produce an HTTP response. */
export class APIConnectionError extends ExtraltError {
  override name = 'APIConnectionError';
}

/** The request timed out on the client. */
export class APITimeoutError extends APIConnectionError {
  override name = 'APITimeoutError';
  constructor(options?: ErrorOptions) {
    super('Request timed out', options);
  }
}

interface ErrorEnvelope {
  code?: string;
  message?: string;
  request_id?: string;
}

/** The API answered with an error status and its stable error envelope. */
export class APIStatusError extends ExtraltError {
  override name = 'APIStatusError';
  readonly status: number;
  readonly code: string | undefined;
  readonly requestId: string | undefined;
  readonly headers: Headers;

  constructor(status: number, headers: Headers, envelope: ErrorEnvelope, fallback: string) {
    const message = envelope.message ?? fallback;
    const requestId = envelope.request_id ?? headers.get('x-request-id') ?? undefined;
    super(
      `${status}${envelope.code ? ` ${envelope.code}` : ''}: ${message}${requestId ? ` (request ${requestId})` : ''}`,
    );
    this.status = status;
    this.code = envelope.code;
    this.requestId = requestId;
    this.headers = headers;
  }
}

export class BadRequestError extends APIStatusError {
  override name = 'BadRequestError';
}
export class AuthenticationError extends APIStatusError {
  override name = 'AuthenticationError';
}
export class PaymentRequiredError extends APIStatusError {
  override name = 'PaymentRequiredError';
}
export class PermissionDeniedError extends APIStatusError {
  override name = 'PermissionDeniedError';
}
export class NotFoundError extends APIStatusError {
  override name = 'NotFoundError';
}
export class ConflictError extends APIStatusError {
  override name = 'ConflictError';
}
export class PayloadTooLargeError extends APIStatusError {
  override name = 'PayloadTooLargeError';
}
export class UnsupportedMediaTypeError extends APIStatusError {
  override name = 'UnsupportedMediaTypeError';
}
export class UnprocessableEntityError extends APIStatusError {
  override name = 'UnprocessableEntityError';
}
export class RateLimitError extends APIStatusError {
  override name = 'RateLimitError';
}
export class InternalServerError extends APIStatusError {
  override name = 'InternalServerError';
}

/** What a Robot, Run, Import or Enrichment reports about its progress. */
export interface Job {
  id: string;
  status: string;
  finished: boolean;
  status_reason?: string | null;
}

/** A Robot build, Run, Import or Enrichment ended as failed. `resource` is its final state. */
export class JobFailedError<T extends Job = Job> extends ExtraltError {
  override name = 'JobFailedError';
  readonly resource: T;
  constructor(message: string, resource: T) {
    super(message);
    this.resource = resource;
  }
}

/**
 * A job did not finish within the call's `timeout`. It keeps running on Extralt. `resource` is its
 * latest state; `wait()` with its id resumes waiting.
 */
export class WaitTimeoutError<T extends Job = Job> extends ExtraltError {
  override name = 'WaitTimeoutError';
  readonly resource: T;
  constructor(message: string, resource: T) {
    super(message);
    this.resource = resource;
  }
}

/** A webhook delivery's headers or signature do not check out. Answer it with a 400. */
export class WebhookVerificationError extends ExtraltError {
  override name = 'WebhookVerificationError';
}

const STATUS_ERRORS: Record<number, typeof APIStatusError> = {
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
};

/** Builds the typed error for an error response, consuming its body. */
export async function statusError(response: Response): Promise<APIStatusError> {
  const text = await response.text().catch(() => '');
  let envelope: ErrorEnvelope = {};
  try {
    const body = JSON.parse(text) as { error?: ErrorEnvelope };
    if (body && typeof body.error === 'object') envelope = body.error;
  } catch {
    // Not the JSON envelope: keep the raw text as the message.
  }
  const ErrorClass =
    STATUS_ERRORS[response.status] ??
    (response.status >= 500 ? InternalServerError : APIStatusError);
  return new ErrorClass(response.status, response.headers, envelope, text || response.statusText);
}
