# web-console · 控制台 (Next.js 15)

完整产品级前端,跑在 http://localhost:3000。

## 特性

- ✅ **多会话** (左侧 sidebar,localStorage 持久化)
- ✅ **流式对话** (token / tool_call / tool_result 实时渲染)
- ✅ **工具调用卡片** (折叠/展开 args + result)
- ✅ **成本看板** (per-message + per-session 累计)
- ✅ **设置抽屉** (API key / backend URL / 模型切换)
- ✅ **健康指示灯** (sidebar 顶部,5s 探测一次)
- ✅ **同源 SSE 代理** (`/api/chat` → backend, 无 CORS 复杂度)
- ✅ **X-Trace-Id 透传** (排障关联 Langfuse)
- ✅ **响应式** (Tailwind v4 zero-config)
- ✅ **0 运行时依赖** (除 next/react)

## 启动

```bash
cd apps/web-console
npm install
npm run dev          # http://localhost:3000
```

需要 backend 在 `http://localhost:8000` (改 BACKEND_URL 环境变量)。

## 生产构建

```bash
npm run build && npm start
```

## 目录结构

```
apps/web-console/
├── app/                            # Next.js App Router
│   ├── page.tsx                    # 主页面 (sidebar + chat + settings)
│   ├── layout.tsx
│   ├── globals.css                 # Tailwind v4 + 字体
│   └── api/
│       ├── chat/route.ts           # SSE 代理 → backend /v1/chat/completions
│       └── health/route.ts         # health 代理
├── components/
│   ├── Sidebar.tsx                 # 会话列表 + 状态灯 + 设置入口
│   ├── ChatPanel.tsx               # 主聊天界面
│   ├── MessageBubble.tsx           # 单条消息 (含统计)
│   ├── ToolCard.tsx                # 工具调用可折叠卡片
│   └── SettingsDrawer.tsx          # 设置抽屉
├── hooks/
│   ├── useAgent.ts                 # SSE 流式状态机
│   ├── useSessions.ts              # 会话 + 持久化
│   └── useSettings.ts              # 用户设置
├── lib/
│   ├── types.ts                    # StreamEvent / UiMessage / Session ...
│   ├── sse.ts                      # SSE parser (CRLF / LF / CR)
│   └── storage.ts                  # localStorage 封装
└── package.json
```

## vs apps/web-lite/chat.html

| 维度 | web-lite | web-console |
|---|---|---|
| 形态 | 单 HTML | Next.js 15 应用 |
| 多会话 | 无 | ✅ |
| 持久化 | 无 | localStorage |
| 工具卡片 | 简单 | 折叠/展开/状态色 |
| 成本展示 | 无 | per-msg + per-session |
| 设置 | 顶部输入框 | 抽屉式 |
| 模型切换 | 无 | datalist 下拉 |
| 适用 | 调试 / API 探索 | 给客户演示 / 内部使用 |
