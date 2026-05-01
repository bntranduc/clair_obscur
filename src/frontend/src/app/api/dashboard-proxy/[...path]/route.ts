import { NextRequest, NextResponse } from "next/server";

/** URL réelle du dashboard FastAPI (HTTP sur EC2 OK) — variable serveur uniquement. */
function upstreamBase(): string {
  return (process.env.DASHBOARD_API_URL || "").replace(/\/+$/, "");
}

function pathForbidden(subPath: string, method: string): NextResponse | null {
  if (!subPath.startsWith("api/v1/")) {
    return NextResponse.json({ error: "path not allowed" }, { status: 403 });
  }
  if (method === "POST" && !subPath.startsWith("api/v1/model/")) {
    return NextResponse.json({ error: "POST path not allowed" }, { status: 403 });
  }
  return null;
}

async function proxyToUpstream(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
  method: "GET" | "POST"
): Promise<NextResponse> {
  const { path } = await context.params;
  const subPath = path.join("/");
  const forbid = pathForbidden(subPath, method);
  if (forbid) return forbid;

  const base = upstreamBase();
  if (!base) {
    return NextResponse.json(
      { error: "DASHBOARD_API_URL is not set (server-side env on Amplify)" },
      { status: 503 }
    );
  }

  const qs = method === "GET" ? request.nextUrl.search : "";
  const target = `${base}/${subPath}${qs}`;

  const headers: Record<string, string> = { Accept: "application/json" };
  let body: ArrayBuffer | undefined;
  if (method === "POST") {
    headers["Content-Type"] = request.headers.get("Content-Type") ?? "application/json";
    body = await request.arrayBuffer();
  }

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method,
      headers,
      body: method === "POST" ? body : undefined,
      cache: "no-store",
    });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return NextResponse.json({ error: "upstream fetch failed", detail: msg }, { status: 502 });
  }

  const ct = upstream.headers.get("Content-Type") ?? "application/json; charset=utf-8";
  const outBody = await upstream.arrayBuffer();
  return new NextResponse(outBody, {
    status: upstream.status,
    headers: { "Content-Type": ct },
  });
}

/**
 * Proxy GET vers l’API dashboard pour éviter le mixed content (HTTPS Amplify → HTTP EC2).
 * Seules les routes ``api/v1/...`` sont autorisées.
 */
export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
): Promise<NextResponse> {
  return proxyToUpstream(request, context, "GET");
}

/** Proxy POST (ex. ``api/v1/model/predict``). */
export async function POST(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
): Promise<NextResponse> {
  return proxyToUpstream(request, context, "POST");
}
