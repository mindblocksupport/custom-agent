/**
 * KB endpoints proxy (Day 8): GET/POST/DELETE → backend /v1/kb/*
 * 透传 multipart 上传和 JSON 响应.
 */

import { NextRequest } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

async function forward(req: NextRequest, path: string[]) {
  const url = `${BACKEND_URL}/v1/kb/${path.join("/")}${req.nextUrl.search}`;
  const auth =
    req.headers.get("authorization") ||
    `Bearer ${process.env.NEXT_PUBLIC_API_KEY || "dev-key-change-me"}`;

  const init: RequestInit = {
    method: req.method,
    headers: {
      Authorization: auth,
    },
  };

  if (req.method !== "GET" && req.method !== "DELETE") {
    const ct = req.headers.get("content-type") || "";
    if (ct.includes("multipart/form-data")) {
      // 透传 form (含 file)
      init.body = req.body as unknown as ReadableStream;
      // @ts-expect-error - Node fetch 需要这个 hint 来 stream body
      init.duplex = "half";
      (init.headers as Record<string, string>)["content-type"] = ct;
    } else {
      init.body = await req.text();
      (init.headers as Record<string, string>)["content-type"] =
        ct || "application/json";
    }
  }

  const upstream = await fetch(url, init);
  return new Response(upstream.body, {
    status: upstream.status,
    headers: { "content-type": upstream.headers.get("content-type") || "application/json" },
  });
}

export async function GET(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  return forward(req, path);
}
export async function POST(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  return forward(req, path);
}
export async function DELETE(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  return forward(req, path);
}
