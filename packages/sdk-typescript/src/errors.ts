/** SDK 错误层级 */

export class AgentError extends Error {
  readonly status?: number;
  readonly body?: string;

  constructor(message: string, opts: { status?: number; body?: string } = {}) {
    super(message);
    this.name = "AgentError";
    this.status = opts.status;
    this.body = opts.body;
  }
}

export class AuthError extends AgentError {
  constructor(message: string, opts?: { status?: number; body?: string }) {
    super(message, opts);
    this.name = "AuthError";
  }
}

export class RateLimitError extends AgentError {
  constructor(message: string, opts?: { status?: number; body?: string }) {
    super(message, opts);
    this.name = "RateLimitError";
  }
}

export class ServerError extends AgentError {
  constructor(message: string, opts?: { status?: number; body?: string }) {
    super(message, opts);
    this.name = "ServerError";
  }
}

export class StreamError extends AgentError {
  constructor(message: string, opts?: { status?: number; body?: string }) {
    super(message, opts);
    this.name = "StreamError";
  }
}

export class TimeoutError extends AgentError {
  constructor(message: string, opts?: { status?: number; body?: string }) {
    super(message, opts);
    this.name = "TimeoutError";
  }
}
