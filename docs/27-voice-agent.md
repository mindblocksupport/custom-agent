# L27 · Voice Agent

> 状态：**讨论中** · v0.1 · 2026-04-22 · $45B 市场重塑，客服 80% 仍走电话

## 0. 为什么独立成章
- **客服 80% 流量仍是电话**——纯文本 Agent 漏掉这块
- $45B 语音 AI 市场转移
- Bland / Vapi / Retell 已成 developer 平台层 ~3 winner
- 垂直 wrapper（healthcare scheduling / debt collection / outbound sales）爆发

## 1. 技术栈

```
┌─────────────────────────────────────┐
│ 电话 / WebRTC 接入                  │
│  Twilio / 阿里云通信 / 腾讯云通信    │
├─────────────────────────────────────┤
│ STT (语音→文本)                     │
│  Whisper / Deepgram / 字节豆包-STT   │
│  目标: <300ms 转录                  │
├─────────────────────────────────────┤
│ LLM (推理)                          │
│  Claude Haiku / GPT-5.4-mini /      │
│  Qwen3-7B (低延迟优先)               │
├─────────────────────────────────────┤
│ TTS (文本→语音)                     │
│  ElevenLabs / OpenAI TTS /          │
│  字节豆包-TTS / 微软 Azure          │
│  目标: <200ms TTFA (首音频)         │
├─────────────────────────────────────┤
│ Voice Agent Orchestration           │
│  Vapi / Retell / Bland / 自建        │
│  P95 必须 <800ms 端到端              │
└─────────────────────────────────────┘
```

## 2. 关键性能指标

| 指标 | 目标 | 备注 |
|---|---|---|
| **TTFA (Time to First Audio)** | <500ms | 用户感知"AI 在听" |
| **总响应延迟** | P95 **<800ms** | 自然对话节奏底线 |
| **STT 延迟** | <300ms | streaming partial transcript |
| **LLM 首 token** | <200ms | 必须流式 |
| **TTS 流式生成** | <100ms 间隔 | chunked synthesis |
| **打断延迟** | <300ms | 用户说话立即停 TTS |
| **回声消除** | 必备 | 否则 Agent 听到自己 |

## 3. 三大开源 / 商业平台对比

| 平台 | 价格 | 形态 | 特点 |
|---|---|---|---|
| **Bland AI** | $0.09/min | 全栈 (自有 STT/LLM/TTS) | 高量出站，infra 控制好 |
| **Vapi** | $0.05/min + components ($0.23-0.33 全包) | dev-first 编排，BYO STT/LLM/TTS | "Stripe for voice" |
| **Retell AI** | $0.07/min flat | 轻量 dev 体验 | 中小 CCaaS 用 |
| **LiveKit Agents** (开源) | 自部署 | 开源框架 | 自建首选 |
| **Pipecat** (开源, Daily.co) | 自部署 | Python 框架 | 开源最活跃 |

## 4. 关键技术挑战

### 4.1 自然对话节奏
- 不是 push-to-talk，是 **continuous streaming**
- VAD (Voice Activity Detection) 决定何时回答
- 半二工 / 全二工：高级要全二工（说同时听）
- 自然停顿（不要总抢话）

### 4.2 打断处理
- 用户随时打断 → 立即停 TTS + clear LLM in-flight
- "barge-in" 是 voice 必备

### 4.3 回声消除
- WebRTC AEC / 硬件 AEC
- 否则 Agent 听到自己的声音又回应

### 4.4 情感 / 语调
- 不只是字 —— TTS 必须传达温度
- ElevenLabs / Azure 高级 TTS 支持 emotion tag

### 4.5 多语言 / 方言
- 中文方言（粤 / 川 / 闽）
- 英文口音
- 中英混说（code-switching）

### 4.6 转人工 (handoff)
- 实时把通话 + context 摘要交给人
- 人接听时听到摘要 → 用户不重复

## 5. 中国语音方案

| 厂商 | 优势 |
|---|---|
| **字节豆包** STT/TTS/LLM | 全栈打包，价格屠夫 |
| **腾讯云语音** | 客服深度 |
| **阿里云智能语音** | 通义集成 |
| **科大讯飞** | 老牌、方言全 |
| **百度智能云** | 国企 / 政府 |

国内方案推荐：**豆包 STT + Qwen3-7B (vLLM) + 豆包 TTS**——延迟 + 成本最优。

## 6. 真实场景

### 6.1 智能客服外呼
- 自动催收 / 提醒 / 营销
- 高合规要求（不能骚扰、必须报身份）
- 中国《通信短信信息服务管理规定》

### 6.2 客服入呼
- IVR 替代 → 直接 LLM 对话
- 复杂问题转人工

### 6.3 医疗预约 / 上门服务调度
- 预约挂号 / 改签 / 提醒
- 美国 PHI 合规 (HIPAA)

### 6.4 销售 SDR
- 冷启动 outbound
- Tavus 视频 + 语音

### 6.5 车机 / 家居
- 端 + 云协同
- 离线兜底

## 7. 合规

- **中国**：通信外呼合规 + 录音 + 内容安全
- **美国 TCPA**：自动外呼必须有 prior express consent
- **EU GDPR**：语音也是 PI
- **录音保留**：行业不同 6 月-7 年
- **AI 身份披露**：很多地区强制 (Utah / Texas 等州法)

## 8. 我们的策略

### 8.1 第一阶段（不重投入）
- 不自建语音平台
- 集成 **Vapi / Retell** (海外) 或 **豆包语音** (国内) 作为 channel
- 我们的 Agent core 通过 webhook / API 提供推理

### 8.2 第二阶段（有 PMF 后）
- 自建 LiveKit / Pipecat 编排
- 控制 latency 与成本

### 8.3 不做
- 自训 STT / TTS 模型（专业厂商更好）

## 9. 实施清单
- [ ] 选定语音 channel 平台（Vapi / 豆包）
- [ ] 我们 Agent → channel webhook 集成
- [ ] 流式 LLM 输出（必须）
- [ ] VAD + 打断处理
- [ ] 回声消除验证
- [ ] 多语言 / 方言测试
- [ ] 转人工 handoff 流程
- [ ] 录音 + 转录 + audit
- [ ] 合规：身份披露 + 录音同意
- [ ] 监控 P95 latency / abandon rate
