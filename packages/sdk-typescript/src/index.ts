/**
 * @custom-agent/sdk · 公开 API
 */

export { Client, Chat, ChatCompletions } from "./client.js";
export type { ClientOptions } from "./client.js";

export {
  AgentError,
  AuthError,
  RateLimitError,
  ServerError,
  StreamError,
  TimeoutError,
} from "./errors.js";

export type {
  ChatChoice,
  ChatCreateParams,
  ChatResponse,
  DoneData,
  DoneEvent,
  ErrorEvent,
  Message,
  Role,
  StartData,
  StartEvent,
  StreamEvent,
  TokenEvent,
  ToolCallData,
  ToolCallEvent,
  ToolResultData,
  ToolResultEvent,
} from "./types.js";

export { parseSSE } from "./sse.js";
export type { SSEEvent } from "./sse.js";
