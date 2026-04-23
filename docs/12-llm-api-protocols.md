# L12 · LLM API 交互协议设计

> 状态：**讨论中** · v0.1 · 2026-04-22 · 我们如何在多个外部 LLM 之上构建统一抽象层

## 0. 为什么这一章必须独立写
"接入 LLM" 不是 `requests.post()` 那么简单。OpenAI / Anthropic / Gemini / Cohere 在工具协议、流式格式、推理输出、缓存、错误码、限流头**全部都不一样**。统一抽象设计是企业 Agent 平台**第一个工程难点**。

## 1. 主流协议家族

| 协议 | 形态 | 关键字段 |
|---|---|---|
| **OpenAI Chat Completions** | `messages: [{role, content}]` | role: system/developer/user/assistant/tool |
| **OpenAI Responses API**（新，agentic） | `input: [Item]`, `output: [Item]` | Items 类型: message, reasoning, function_call, web_search_call, file_search_call, computer_call, mcp_call |
| **Anthropic Messages** | content-block native | content: [text/image/document/tool_use/tool_result/thinking/redacted_thinking] |
| **Google Gemini** | `contents: [Content]` (Protobuf 形) | role: "user"/"model" (注意不是 assistant); parts: [text/inlineData/functionCall/functionResponse/thought] |
| **Cohere v2 Chat** | OpenAI 形 + Cohere RAG-native | citations 一等公民; tool_plan 字段 |

### "OpenAI 兼容"的暗坑
DeepSeek / Qwen / Kimi / GLM 都声称 OpenAI 兼容，但每家加了私货：
- **DeepSeek**: `deepseek-reasoner` 返回 `message.reasoning_content`，传回会 400；reasoner 静默忽略 temperature/top_p/penalty/logprobs
- **Qwen**: `enable_thinking` 通过 `extra_body`；hybrid thinking 模型也吐 `reasoning_content`
- **Kimi**: 自定义 `kimi-cache-id` header 管 cache 生命周期
- **GLM-4.6**: `thinking: {type: "disabled"}` 才关思考；默认开
- **统一抽象层必须感知这些差异**

## 2. Tool / Function Calling 差异（最大的坑）

| 维度 | OpenAI | Anthropic | Gemini | Cohere |
|---|---|---|---|---|
| Tool 定义 | `{type:"function", function:{name, description, parameters}}` | `{name, description, input_schema}` | `{functionDeclarations:[{name, description, parameters}]}` | OpenAI 形 |
| Schema 方言 | JSON Schema (strict 子集) | JSON Schema | OpenAPI 3.0 子集 | JSON Schema |
| `tool_choice` | `none/auto/required/{name}` | `{type:"auto/any/tool/none", name?, disable_parallel?}` | `mode: AUTO/ANY/NONE/VALIDATED + allowedFunctionNames` | `REQUIRED/NONE` only |
| 并行调用 | `parallel_tool_calls: true` 默认 | `disable_parallel_tool_use` 反向 | 隐式（多个 functionCall part） | 是 |
| **工具结果 role** | `role:"tool", tool_call_id` | `role:"user"`, content `[tool_result]` block | `role:"user"`, parts `[functionResponse]` | OpenAI 形 |
| ID 关联 | `tool_calls[i].id` ↔ tool message `tool_call_id` | `tool_use.id` ↔ `tool_result.tool_use_id` | `functionCall.id` ↔ `functionResponse.id` | 同 OpenAI |

**最难映射**：role placement。OpenAI/Cohere 有 `tool` role；Anthropic/Gemini 把结果放 `user` role 的 typed block 里。统一抽象必须无损来回。

## 3. 流式（SSE）差异

### OpenAI Chat Completions
```
data: {chunk}\n\n
...
data: [DONE]
```
- `delta.tool_calls[i]` 按 `index` 累积，partial JSON 字符串拼接
- usage 仅在 `stream_options.include_usage: true` 时末尾返回

### OpenAI Responses
**typed event** 而非 opaque delta：
- `response.created / in_progress / output_item.added / content_part.added / output_text.delta / function_call_arguments.delta / reasoning.delta / output_item.done / completed / failed / incomplete / error`
- 每事件带 `sequence_number` + `item_id`

### Anthropic
**命名 SSE 事件**严格顺序：
```
message_start
  → (per content block: content_block_start → N×content_block_delta → content_block_stop)
  → message_delta (含最终 stop_reason + cumulative usage)
  → message_stop
```
- delta types: `text_delta`, `input_json_delta` (partial tool args), `thinking_delta`, `signature_delta`, `citations_delta`
- 中途 error 是 SSE event 而非 HTTP（**overloaded_error 是 mid-stream，不是 529**）

### Gemini
- `?alt=sse` 才返 SSE；不带就返单一 JSON 数组（坑）
- 每 event = 完整 GenerateContentResponse 形，partial 在 `candidates[0].content.parts[0].text`
- 无 sentinel；连接关闭终止

### 统一策略
内部用 **Anthropic-style 事件模型**（最表达力）：
```
message_start → block_start → text_delta/json_delta/thinking_delta → block_stop → message_delta(usage,finish) → message_stop | error
```
- OpenAI Chat delta → 提升 `delta.content` 为 `text_delta`，`tool_calls[i].function.arguments` 为 `input_json_delta`
- OpenAI Responses typed event 几乎 1:1
- Gemini parts 解析合成 start/delta/stop 事件

## 4. Reasoning / Extended Thinking

| 厂商 | 字段 | 注意 |
|---|---|---|
| OpenAI o3/GPT-5.x (Chat) | `completion_tokens_details.reasoning_tokens`（计费但不返） | - |
| OpenAI Responses | `output` 含 `reasoning` item (`summary` parts + `encrypted_content`) | stateless 时回传 encrypted_content |
| Anthropic | `thinking: {type:"enabled", budget_tokens: 10000}` 或 `adaptive` | 返 `thinking` block 带 cryptographic `signature`；redacted 时返 `redacted_thinking`；**signature 必须原封不动回传**（特别 tool use 时）；`interleaved-thinking-2025-05-14` beta header 允许工具间思考 |
| DeepSeek-R1 | `message.reasoning_content` 兄弟字段 | **不能回传**否则 400 |
| Qwen / GLM | 同 R1 模式；`enable_thinking` (Qwen) 或 `thinking.type` (GLM) | - |
| Gemini | `thinkingConfig: {thinkingBudget, includeThoughts}` | 开 includeThoughts 后 reasoning 在 `parts[i].thought=true` |

**统一抽象需要 3 个正交标志**：`(reasoning_enabled, reasoning_budget, reveal_to_user)` + 不透明 `_provider_reasoning_state` 用于回传。

## 5. 结构化输出

| 厂商 | 机制 | 强度 |
|---|---|---|
| OpenAI Structured Outputs | `response_format: {type:"json_schema", json_schema:{name, schema, strict:true}}` | strict=true 时**保证**符合 schema（CFG/token-mask） |
| Anthropic | `output_config.format: {type:"json_schema"}` (2025-Q4 起) | 受支持模型 constrained decoding |
| Gemini | `generationConfig.responseSchema + responseMimeType:"application/json"` | OpenAPI 3.0 子集 |
| Cohere | `response_format:{type:"json_object", schema}` + `strict_tools` | - |
| 开源 | Outlines / Instructor / FORMATRON / llama.cpp grammars | client-side constrained sampling |

**注意**：strict=true 模式有限制（root 不能 `anyOf`，每个 prop 必须 required，`format/pattern/minLength` 不支持）。

## 6. Prompt Caching（**最大的省钱点**）

| 厂商 | 机制 | 价格 |
|---|---|---|
| Anthropic | 显式 `cache_control:{type:"ephemeral", ttl:"5m"或"1h"}`，最多 4 breakpoints, 1024-4096 token 起步 | 5min write 1.25× / 1h write 2× / **read 0.1×**；usage 报 `cache_creation_input_tokens`, `cache_read_input_tokens`, `cache_creation:{ephemeral_5m, ephemeral_1h}`；**改 tools 全 cache 失效** |
| OpenAI | 自动 (>1024 token) | 5-10min TTL；50% off；usage 报 `prompt_tokens_details.cached_tokens`；Responses 用 `prompt_cache_key` 影响路由 |
| Gemini | 隐式（2.5+ 默认）+ 显式 `cachedContents` 资源 | 90% off；显式按小时存储计费；`usageMetadata.cachedContentTokenCount` |
| Kimi | 自定义 header `kimi-cache-id` | - |

**通用优化原则**：可缓存内容（tools → system → 静态 context → exemplars）放**前缀稳定**位置，所有易变（时间戳、用户问题）放尾部。

## 7. 多模态输入

| 模态 | OpenAI | Anthropic | Gemini |
|---|---|---|---|
| 图像 | `image_url` (URL or base64) | `{type:"image", source:{type, data, media_type}}` | `inlineData:{mimeType, data}` 或 `fileData` |
| PDF | upload `file_id` 或 Responses file_search | `{type:"document", source}` （native，带 citations） | `fileData` after Files API upload |
| 音频输入 | `input_audio` (gpt-4o-audio) | 不 native | `inlineData:{mimeType:"audio/..."}` |
| 音频输出 | `modalities:["audio"]` | n/a | n/a |
| 视频 | 抽帧 | n/a | `fileData` (mp4/webm) + `videoMetadata` |

## 8. 错误处理 & 重试

| 厂商 | 限流码 | Retry-After | 限流头 | 幂等 |
|---|---|---|---|---|
| OpenAI | 429 + Retry-After | 是 | `x-ratelimit-{limit, remaining, reset}-{requests, tokens}` | `Idempotency-Key` (Responses) |
| Anthropic | 429 = rate_limit_error；**529 = overloaded**（独立！） | 是 | `anthropic-ratelimit-*` 一系列 | `Idempotency-Key` 支持；每响应带 `request-id` |
| Gemini | Google 标准 (400/403/429/500/503) | RetryInfo 详情 | 项目 + 区域 quotas | - |
| Cohere | 429 + Retry-After；流中失败 `finish_reason: ERROR` | 是 | - | - |

**通用重试**：
- 严格遵守 `Retry-After`
- 否则 jittered 指数退避（initial 1s，base 2，max 60s，cap 5 次）
- 重试 `429/500/502/503/504/529`
- 永不重试 `400/401/403/404/422`
- 流中 `error` event 等同 HTTP 错误处理

## 9. 其他关键

| 项 | OpenAI | Anthropic | Gemini | Cohere |
|---|---|---|---|---|
| logprobs | `logprobs:true, top_logprobs` | 不暴露 | `responseLogprobs` | `logprobs:true` |
| stop sequences | `stop` (≤4) | `stop_sequences` | `stopSequences` (≤5) | `stop_sequences` (≤5) |
| 采样 | temp, top_p; 不 top_k | temp, top_p, top_k | temp, top_p, top_k | temp, top_p, top_k |
| 频率惩罚 | freq_penalty, presence_penalty | 无 | 同 OpenAI | 同 OpenAI |
| system message | `role:"system"` 或 `developer` (Chat); top-level `instructions` (Responses) | top-level `system` (str 或 cacheable block array) | top-level `systemInstruction` | `role:"system"` |
| max tokens | `max_completion_tokens` (含 reasoning) | `max_tokens` (必填) | `maxOutputTokens` | `max_tokens` |

## 10. 统一抽象层设计（推荐）

LiteLLM 模式 = "薄 OpenAI-compatible 外观"，~80% 场景 OK，但**丢失** Anthropic content block / Responses items / Gemini parts / citations / signatures / TTL 缓存。

### 推荐双层抽象

#### Layer A · 内部富 native schema（**Anthropic-style content block 是最佳超集**）

```python
class Message:
    role: Literal["system", "user", "assistant", "tool"]
    content: list[ContentBlock]  # text | image | document | audio | tool_use | tool_result | reasoning | citation
    cache_hint: dict | None  # {ttl: "5m" | "1h"}

class Request:
    model: str
    system: str | list[ContentBlock]
    messages: list[Message]
    tools: list[Tool]
    tool_choice: Literal["auto","required","none"] | dict
    sampling: SamplingParams  # temp, top_p, top_k, stop, freq/pres penalty
    max_output_tokens: int
    reasoning: ReasoningConfig  # enabled, budget, reveal
    response_format: dict  # type, schema, strict
    cache_policy: dict
    stream: bool
    metadata: dict  # tenant_id, user_id, biz_tag
    idempotency_key: str | None
    _provider_passthrough: dict  # 厂商专属，原样转
```

#### Layer B · 厂商适配器
每个 adapter 负责：
1. **请求转换**
2. **SSE 解析**（→ 统一事件流）
3. **usage 归一化**为单一 `{input_tokens, output_tokens, cached_input_tokens, reasoning_tokens, cache_write_tokens_5m, cache_write_tokens_1h}`
4. **错误分类**为 `{rate_limit, overloaded, invalid_input, auth, server, content_filter, timeout}`
5. **能力矩阵广播** `{supports_strict_json, supports_native_pdf, supports_parallel_tools, max_image_size, ...}` —— orchestrator 据此路由 / 降级

### 抽象必须"漏"的地方
- `_provider_passthrough` 字段保留（`enable_thinking`, `safety_mode`, `service_tier`, `interleaved-thinking` beta 等）
- 响应带 `_provider_extras`，让上层决策

### 推荐对外双 API
- **OpenAI-compatible 外观**（`/v1/chat/completions` + `/v1/responses`）—— 客户已用 OpenAI SDK 直接切
- **Anthropic-Messages-compatible 外观**（`/v1/messages`）—— content block / cache_control / thinking / signature 原生支持
- 都内部走 Layer A，零热路径有损翻译

## 11. 实施清单

- [ ] Layer A schema 锁定
- [ ] OpenAI / Anthropic / Gemini / Cohere / DeepSeek / Qwen / GLM / Kimi 8 个 adapter
- [ ] 统一 SSE 事件模型 + parser
- [ ] 错误分类表 + 重试策略
- [ ] usage 归一化 + 计费写库
- [ ] capability matrix（能力广播表）
- [ ] OpenAI-compat + Anthropic-compat 双外观
- [ ] Cache-control 自动切 5m/1h（按 prefix 重用频率）
- [ ] Idempotency 全链路传递
- [ ] OTel GenAI semantic conventions span 自动埋点

## 12. 参考实现
- LiteLLM `/v1/messages` mode（Anthropic-compat 外观）
- Bifrost / TensorZero（Rust 高性能参考）
- Vercel AI SDK 6（TS 上层抽象）

## 13. 真实坑总结
1. 不同模型 tokenizer 不同 → token 计算偏差 10-30%
2. "OpenAI 兼容"是营销话术——每家都有私货
3. 流式协议互不兼容，做适配层时 Anthropic event 模型最表达力
4. Prompt cache 是省钱第一杠杆——架构必须从一开始考虑前缀稳定
5. Reasoning 字段千差万别，DeepSeek 回传会报错
6. Anthropic signature 必须原样回传——丢了就算违例
7. 价格 6 个月降 5-10×，计费表必须可热更新
8. 国内 API 经常白天高峰几秒延迟——必须 multi-vendor failover
