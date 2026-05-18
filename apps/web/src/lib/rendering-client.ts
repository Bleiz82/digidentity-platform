/**
 * HTTP client for POST /api/v1/rendering/decide — BIBLE-v3 §6.2.
 * Validates the response with Zod to fail fast on schema drift.
 */

import {
  decideResponseSchema,
  type DecideResponse,
  type VisitorPriorInput,
} from "@/types/rendering";

const API_BASE =
  typeof process !== "undefined"
    ? (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000")
    : "http://localhost:8000";

export async function fetchDirectives(
  prior: VisitorPriorInput,
  target_page: string,
  pack_id: string,
  tenant_id: string
): Promise<DecideResponse> {
  const resp = await fetch(`${API_BASE}/api/v1/rendering/decide`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Tenant-Id": tenant_id,
    },
    body: JSON.stringify({ prior, target_page, pack_id }),
  });

  if (!resp.ok) {
    throw new Error(`rendering/decide ${resp.status}: ${resp.statusText}`);
  }

  const raw: unknown = await resp.json();
  return decideResponseSchema.parse(raw);
}
