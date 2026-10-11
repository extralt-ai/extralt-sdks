/** Receives the client's log lines, such as `console` or an application logger. */
export interface Logger {
  debug(message: string): void;
  info(message: string): void;
}

/** `debug` logs every response and retry, `info` only retries. */
export type LogLevel = 'debug' | 'info' | 'off';

const consoleLogger: Logger = {
  debug: (message) => console.debug(`extralt ${message}`),
  info: (message) => console.info(`extralt ${message}`),
};

const ignore = (): void => {};

/** A logger that only passes on the lines `level` enables. API keys are never logged. */
export function levelledLogger(level: LogLevel, logger: Logger = consoleLogger): Logger {
  return {
    debug: level === 'debug' ? (message) => logger.debug(message) : ignore,
    info: level === 'off' ? ignore : (message) => logger.info(message),
  };
}

/** The level `EXTRALT_LOG` selects, as in the Python SDK. */
export function logLevel(value: string | undefined): LogLevel {
  const level = value?.toLowerCase();
  return level === 'debug' || level === 'info' ? level : 'off';
}
