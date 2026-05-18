import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { parseUtm, parseReferrer, parseDevice, inferPersona } from "@/lib/sense/rules";

export const config = { matcher: ["/demo/:path*"] };

const COOKIE_NAME = "dg_visitor_prior";
const COOKIE_MAX_AGE = 1800;
const TENANT_ID = "00000000-0000-0000-0000-000000000001";

export function middleware(request: NextRequest): NextResponse {
  const response = NextResponse.next();

  const sessionId = request.cookies.get("dg_session_id")?.value ?? crypto.randomUUID();
  response.cookies.set("dg_session_id", sessionId, {
    httpOnly: false,
    sameSite: "lax",
    maxAge: COOKIE_MAX_AGE,
    path: "/",
  });
  response.headers.set("x-dg-session-id", sessionId);

  const existing = request.cookies.get(COOKIE_NAME)?.value;
  if (existing) return response;

  const url = new URL(request.url);
  const utm = parseUtm(url.searchParams);
  const referrer = parseReferrer(request.headers.get("referer"));
  const ua = request.headers.get("user-agent") ?? "";
  const device = parseDevice(ua);
  const inferred_personas = inferPersona({ utm, referrer, device });

  const visitorHash = (() => {
    const raw = `${ua}|${request.headers.get("accept-language") ?? ""}`;
    let h = 0;
    for (let i = 0; i < raw.length; i++) {
      h = (Math.imul(31, h) + raw.charCodeAt(i)) | 0;
    }
    return Math.abs(h).toString(16).padStart(16, "0");
  })();

  const prior = {
    session_id: sessionId,
    tenant_id: TENANT_ID,
    visitor_hash: visitorHash,
    inferred_personas,
    signals: {
      device_class: device.device_type,
      utm,
      is_returning: false,
      referrer: referrer.referrer_domain || null,
      language: request.headers.get("accept-language")?.split(",")[0] ?? null,
    },
    confidence: inferred_personas[0]?.score ?? 0.1,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };

  const serialized = JSON.stringify(prior);
  if (serialized.length < 4000) {
    response.cookies.set(COOKIE_NAME, serialized, {
      httpOnly: false,
      sameSite: "lax",
      maxAge: COOKIE_MAX_AGE,
      path: "/",
    });
  }

  return response;
}
