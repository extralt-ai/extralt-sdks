/** A binary download. Consume the body once, or call `cancel()` to release it. */
export class BinaryResponse {
  readonly response: Response;

  constructor(response: Response) {
    this.response = response;
  }

  get contentType(): string | null {
    return this.response.headers.get('content-type');
  }

  get fileName(): string | null {
    const disposition = this.response.headers.get('content-disposition') ?? '';
    return /filename="?([^";]+)"?/.exec(disposition)?.[1] ?? null;
  }

  /** The streamed body, for example `Readable.fromWeb(download.body)` in Node.js. */
  get body(): ReadableStream<Uint8Array> {
    if (!this.response.body) throw new TypeError('The response has no body');
    return this.response.body;
  }

  arrayBuffer(): Promise<ArrayBuffer> {
    return this.response.arrayBuffer();
  }

  text(): Promise<string> {
    return this.response.text();
  }

  async cancel(): Promise<void> {
    await this.response.body?.cancel();
  }
}
