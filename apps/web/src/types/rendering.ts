/**
 * TypeScript types mirroring Python RenderingDirective / DecideResponse — BIBLE-v3 §7.2.
 * Validated with Zod to match the backend contract from api/rendering.py.
 */

import { z } from "zod";

export const directiveTypeSchema = z.enum([
  "morph_section",
  "highlight",
  "inject",
  "set_persona",
  "show",
  "hide",
  "reorder",
  "rewrite_copy",
]);

export type DirectiveType = z.infer<typeof directiveTypeSchema>;

export const renderingDirectiveSchema = z.object({
  type: directiveTypeSchema,
  target: z.string().min(1),
  params: z.record(z.unknown()).default({}),
  priority: z.number().int().min(0).max(1000).default(100),
  reason: z.string(),
});

export type RenderingDirective = z.infer<typeof renderingDirectiveSchema>;

export const decideResponseSchema = z.object({
  directives: z.array(renderingDirectiveSchema),
  matched_rules: z.array(z.string()),
  latency_ms: z.number(),
});

export type DecideResponse = z.infer<typeof decideResponseSchema>;

export interface VisitorPriorInput {
  session_id: string;
  tenant_id: string;
  visitor_hash: string;
  inferred_personas: Array<{ persona_id: string; score: number }>;
  signals: {
    device_class?: string;
    utm?: Record<string, string>;
    is_returning?: boolean;
    referrer?: string | null;
    geo_city?: string | null;
    language?: string | null;
  };
  confidence?: number;
  created_at: string;
  updated_at: string;
}
