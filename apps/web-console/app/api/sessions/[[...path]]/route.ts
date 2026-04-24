/**
 * Sessions endpoints proxy (Day 8): GET/POST/DELETE/PATCH → backend /v1/sessions/*
 */

import { NextRequest } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

async function forward(req: NextRequest, path: string[]) {
  const suffix = path.join("/");
  const url = `${BACKEND_URL}/v1/sessions${suffix ? "/" + suffix : ""}${req.nextUrl.search}`;
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
    headers: {
      "content-type": upstream.headers.get("content-type") || "application/json",
    },
  });
}

export async function GET(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  return forward(req, path ?? []);
}
export async function POST(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  return forward(req, path ?? []);
}
export async function DELETE(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  return forward(req, path ?? []);
}
export async function PATCH(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  return forward(req, path ?? []);
}
