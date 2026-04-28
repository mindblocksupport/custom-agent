/**
 * 与服务端 packages/schemas/events.py + SDK 保持一致。
 */

export type Role = "system" | "user" | "assistant" | "tool";

export interface ApiMessage {
  role: Role;
  /**
   * - string: 纯文本 (主路径)
   * - ContentPart[]: multimodal — 文本 + 图片混排 (vision-capable model)
   * - null: tool 消息
   */
  content?: string | ContentPart[] | null;
  tool_calls?: Array<Record<string, unknown>> | null;
  tool_call_id?: string | null;
}

export type ContentPart =
  | { type: "text"; text: string }
  | { type: "image_url"; image_url: { url: string } };

/** 用户附件 (本地未发送 / 已发送两种状态都用此结构) */
export interface UserAttachment {
  id: string;
  /** 直接 base64 data URL 或 http(s) URL */
  dataUrl: string;
  filename: string;
  /** bytes (估算) */
  size: number;
  mime: string;
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

// ============================================================
// Day 11/8 新增: retrieval 事件 (搜索过程可视化)
// ============================================================
export interface CitationData {
  doc_id: string;
  chunk_id: string;
  source_uri: string;
  title?: string | null;
  page?: number | null;
  char_offset_start?: number | null;
  char_offset_end?: number | null;
  score: number;
  snippet: string;
}

export interface RetrievalStartData {
  tool_call_id?: string | null;
  query: string;
  k: number;
}
export interface RetrievalStartEvent {
  type: "retrieval.start";
  data: RetrievalStartData;
}

export interface RetrievalDoneData {
  tool_call_id?: string | null;
  citations: CitationData[];
  refused: boolean;
  refusal_reason?: string | null;
  n_dense: number;
  n_bm25: number;
  n_rerank_in: number;
  elapsed_ms?: number | null;
}
export interface RetrievalDoneEvent {
  type: "retrieval.done";
  data: RetrievalDoneData;
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
  | RetrievalStartEvent
  | RetrievalDoneEvent
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
  // Day 8: search_kb 富化字段 (来自 retrieval.start / retrieval.done)
  retrievalQuery?: string;
  citations?: CitationData[];
  refused?: boolean;
  refusalReason?: string | null;
  elapsedMs?: number | null;
  nDense?: number;
  nBm25?: number;
  nRerankIn?: number;
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
  /** 仅 user 消息: 附件 (图片) */
  attachments?: UserAttachment[];
  /** 完成后的统计 */
  done?: DoneData;
  /** error 信息 */
  error?: string;
  createdAt: number;
  // Day 8: chat 路由元信息 (来自响应头)
  traceId?: string;
  routeReason?: string;
  model?: string;
  sessionId?: string;
}

export interface Session {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messageCount: number;
  totalCostUsd: number;
  tags?: string[];
}

export interface Settings {
  apiKey: string;
  baseUrl: string;
  model: string;
}

// ============================================================
// Day 8: KB 类型
// ============================================================
export interface KbDoc {
  id: string;
  source_uri: string;
  source_type: string;
  title?: string | null;
  collection: string;
  status: string;
  current_version: number;
  chunk_count: number;
  created_at: string;
  updated_at: string;
}

export interface KbJob {
  id: string;
  doc_id?: string | null;
  collection: string;
  source_uri: string;
  status: "pending" | "parsing" | "chunking" | "embedding" | "done" | "failed";
  progress: number;
  stage?: string | null;
  error?: string | null;
  chunks_created: number;
  chunks_reused: number;
  created_at: string;
  finished_at?: string | null;
}

// ============================================================
// v1.5 沉淀层: Workspace + Skill
// ============================================================
export interface Workspace {
  id: string;
  name: string;
  description: string;
  default_model: string;
  allowed_models: string[];
  allowed_tools: string[];
  default_collection: string;
  allowed_collections: string[];
  budget_daily_usd: number | null;
  budget_monthly_usd: number | null;
  features: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface Skill {
  id: string;
  workspace_id: string;
  name: string;
  description: string;
  version: number;
  system_prompt: string;
  allowed_tools: string[];
  default_collections: string[];
  starter_examples: string[];
  visibility: "private" | "workspace" | "public";
  budget_per_call_usd: number | null;
  tags: string[];
  created_at: string;
  updated_at: string;
}
