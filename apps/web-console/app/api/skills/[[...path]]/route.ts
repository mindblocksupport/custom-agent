/** Skills 代理 → 后端 /v1/skills/* */
import { NextRequest } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

async function forward(req: NextRequest, path: string[]) {
  const suffix = path.join("/");
  const url = `${BACKEND_URL}/v1/skills${suffix ? "/" + suffix : ""}${req.nextUrl.search}`;
  const auth =
    req.headers.get("authorization") ||
    `Bearer ${process.env.NEXT_PUBLIC_API_KEY || "dev-key-change-me"}`;
  const init: RequestInit = {
    method: req.method,
    headers: {
      Authorization: auth,
      "Content-Type": req.headers.get("content-type") || "application/json",
    },
  };
  if (req.method !== "GET" && req.method !== "DELETE") {
    init.body = await req.text();
  }
  const upstream = await fetch(url, init);
  return new Response(upstream.body, {
    status: upstream.status,
    headers: { "content-type": upstream.headers.get("content-type") || "application/json" },
  });
}
export async function GET(req: NextRequest, c: { params: Promise<{ path: string[] }> }) { return forward(req, (await c.params).path ?? []); }
export async function POST(req: NextRequest, c: { params: Promise<{ path: string[] }> }) { return forward(req, (await c.params).path ?? []); }
export async function PATCH(req: NextRequest, c: { params: Promise<{ path: string[] }> }) { return forward(req, (await c.params).path ?? []); }
export async function DELETE(req: NextRequest, c: { params: Promise<{ path: string[] }> }) { return forward(req, (await c.params).path ?? []); }
