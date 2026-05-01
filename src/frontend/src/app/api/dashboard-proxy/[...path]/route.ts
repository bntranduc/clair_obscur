import { NextRequest, NextResponse } from "next/server";

/** URL réelle du dashboard FastAPI (HTTP sur EC2 OK) — variable serveur uniquement. */
function upstreamBase(): string {
  return (process.env.DASHBOARD_API_URL || "").replace(/\/+$/, "");
}

/**
 * Proxy GET vers l’API dashboard pour éviter le mixed content (HTTPS Amplify → HTTP EC2).
 * Seules les routes ``api/v1/...`` sont autorisées.
 */
export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
): Promise<NextResponse> {
  const { path } = await context.params;
  const subPath = path.join("/");
  if (!subPath.startsWith("api/v1/")) {
    return NextResponse.json({ error: "path not allowed" }, { status: 403 });
  }

  const base = upstreamBase();
  if (!base) {
    return NextResponse.json(
      { error: "DASHBOARD_API_URL is not set (server-side env on Amplify)" },
      { status: 503 }
    );
  }

  const target = `${base}/${subPath}${request.nextUrl.search}`;
  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: "GET",
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return NextResponse.json({ error: "upstream fetch failed", detail: msg }, { status: 502 });
  }

  const ct = upstream.headers.get("Content-Type") ?? "application/json; charset=utf-8";
  const body = await upstream.arrayBuffer();
  return new NextResponse(body, {
    status: upstream.status,
    headers: {
      "Content-Type": ct,
    },
  });
}
