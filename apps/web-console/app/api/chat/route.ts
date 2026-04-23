/**
 * SSE proxy: 浏览器 → 本路由 → backend (api-server)
 *
 * 用 Next.js 同源代理避免 CORS 复杂度。
 * 透传 X-Trace-Id (从 backend 过来) 给前端,排障可关联 Langfuse。
 */

import { NextRequest } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

export async function POST(req: NextRequest) {
  const body = await req.json();
  const auth =
    req.headers.get("authorization") ||
    `Bearer ${process.env.NEXT_PUBLIC_API_KEY || "dev-key-change-me"}`;

  const upstream = await fetch(`${BACKEND_URL}/v1/chat/completions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: auth,
    },
    body: JSON.stringify({ ...body, stream: true }),
  });

  if (!upstream.ok) {
    const errText = await upstream.text();
    return new Response(errText, {
      status: upstream.status,
      headers: { "Content-Type": "text/plain" },
    });
  }

  const headers = new Headers({
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache, no-transform",
    Connection: "keep-alive",
  });
  const traceId = upstream.headers.get("x-trace-id");
  if (traceId) headers.set("X-Trace-Id", traceId);

  return new Response(upstream.body, { headers });
}
