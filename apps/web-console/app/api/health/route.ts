/** Health proxy → backend */

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

export async function GET() {
  try {
    const r = await fetch(`${BACKEND_URL}/health/`);
    return new Response(await r.text(), {
      status: r.status,
      headers: { "Content-Type": r.headers.get("content-type") ?? "application/json" },
    });
  } catch (e) {
    return new Response(JSON.stringify({ status: "down", error: String(e) }), {
      status: 503,
      headers: { "Content-Type": "application/json" },
    });
  }
}
