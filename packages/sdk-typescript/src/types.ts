/**
 * SDK 类型定义
 *
 * 与 Python SDK 的 types.py、服务端 packages/schemas 保持一致。
 */

// ============================================================
// Chat Messages (OpenAI 兼容)
// ============================================================
export type Role = "system" | "user" | "assistant" | "tool";

export interface Message {
  role: Role;
  content?: string | null;
  tool_calls?: Array<Record<string, unknown>> | null;
  tool_call_id?: string | null;
}

export interface ChatChoice {
  index: number;
  message: Message;
  finish_reason?: string | null;
}

export interface ChatResponse {
  model: string;
  choices: ChatChoice[];
}

// ============================================================
// Stream Events (discriminated union)
// ============================================================
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
  arguments: string; // JSON string (LLM 原样输出)
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

/** 所有流式事件的 discriminated union (按 `type` 区分)。 */
export type StreamEvent =
  | StartEvent
  | TokenEvent
  | ToolCallEvent
  | ToolResultEvent
  | DoneEvent
  | ErrorEvent;

// ============================================================
// Request shapes
// ============================================================
export interface ChatCreateParams {
  messages: Message[];
  model?: string;
  temperature?: number;
  max_tokens?: number;
  metadata?: Record<string, unknown>;
}
