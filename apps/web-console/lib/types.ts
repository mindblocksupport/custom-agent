/**
 * 与服务端 packages/schemas/events.py + SDK 保持一致。
 */

export type Role = "system" | "user" | "assistant" | "tool";

export interface ApiMessage {
  role: Role;
  content?: string | null;
  tool_calls?: Array<Record<string, unknown>> | null;
  tool_call_id?: string | null;
}

export interface StartData {
  model: string;
  max_steps: number;
}
export interface StartEvent {
  type: "start";
  data: StartData;
}

export interface TokenEvent {
  type: "token";
  text: string;
}

export interface ToolCallData {
  id?: string | null;
  name: string;
  arguments: string;
}
export interface ToolCallEvent {
  type: "tool_call";
  data: ToolCallData;
}

export interface ToolResultData {
  id?: string | null;
  name: string;
  result?: string | null;
  error?: string | null;
}
export interface ToolResultEvent {
  type: "tool_result";
  data: ToolResultData;
}

export interface DoneData {
  steps: number;
  cost_usd: number;
  input_tokens?: number;
  output_tokens?: number;
}
export interface DoneEvent {
  type: "done";
  data: DoneData;
}

export interface ErrorEvent {
  type: "error";
  text: string;
}

export type StreamEvent =
  | StartEvent
  | TokenEvent
  | ToolCallEvent
  | ToolResultEvent
  | DoneEvent
  | ErrorEvent;

// ============================================================
// UI 内部模型 (区别于线上 ApiMessage)
// ============================================================
export type UiBlockKind = "text" | "tool" | "error";

export interface ToolInvocation {
  id: string; // local uuid
  callId?: string | null; // server tool_call_id
  name: string;
  argumentsRaw: string;
  status: "running" | "ok" | "error";
  result?: string;
  error?: string;
}

export interface UiMessage {
  id: string;
  role: Role;
  /** 一条 assistant 消息可能包含多段 text + tool 交错 */
  blocks: Array<
    | { kind: "text"; text: string }
    | { kind: "tool"; invocation: ToolInvocation }
  >;
  /** 仅 user 消息用 */
  text?: string;
  /** 完成后的统计 */
  done?: DoneData;
  /** error 信息 */
  error?: string;
  createdAt: number;
}

export interface Session {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messageCount: number;
  totalCostUsd: number;
}

export interface Settings {
  apiKey: string;
  baseUrl: string;
  model: string;
}
