import { z } from "zod";

// Directive types matching the real backend SSE contract (llm_router.py)
export type DirectiveType =
  | "text"
  | "stream_interrupted"
  | "stream_complete"
  | "ping";

export interface BaseDirective {
  type: DirectiveType;
  timestamp?: number;
}

// Backend emits: {"type": "text", "text": "<chunk>"}
export interface TextDirective extends BaseDirective {
  type: "text";
  text: string;
}

// Backend emits: {"type": "stream_interrupted", "retry": true|false}
export interface StreamInterruptedDirective extends BaseDirective {
  type: "stream_interrupted";
  retry: boolean;
  reason?: string;
}

// Backend does not currently emit stream_complete (stream ends by closing the
// SSE connection). Kept in types for forward compatibility when backend adds it.
export interface StreamCompleteDirective extends BaseDirective {
  type: "stream_complete";
  total_tokens?: number;
}

export interface PingDirective extends BaseDirective {
  type: "ping";
}

export type Directive =
  | TextDirective
  | StreamInterruptedDirective
  | StreamCompleteDirective
  | PingDirective;

const baseFields = {
  timestamp: z.number().optional(),
};

export const directiveSchema = z.discriminatedUnion("type", [
  z.object({
    ...baseFields,
    type: z.literal("text"),
    text: z.string(),
  }),
  z.object({
    ...baseFields,
    type: z.literal("stream_interrupted"),
    retry: z.boolean(),
    reason: z.string().optional(),
  }),
  z.object({
    ...baseFields,
    type: z.literal("stream_complete"),
    total_tokens: z.number().optional(),
  }),
  z.object({
    ...baseFields,
    type: z.literal("ping"),
  }),
]);
