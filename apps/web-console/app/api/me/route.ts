/** /v1/me proxy */

import { NextRequest } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

export async function GET(req: NextRequest) {
  const auth =
    req.headers.get("authorization") ||
    `Bearer ${process.env.NEXT_PUBLIC_API_KEY || "dev-key-change-me"}`;
  const upstream = await fetch(`${BACKEND_URL}/v1/me`, {
    headers: { Authorization: auth, "Content-Type": "application/json" },
  });
  return new Response(upstream.body, {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}
