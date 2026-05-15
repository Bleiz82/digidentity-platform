import { z } from "zod";

export type DirectiveType =
  | "text_chunk"
  | "tool_call"
  | "tool_result"
  | "stream_complete"
  | "stream_interrupted"
  | "ping";

export interface BaseDirective {
  type: DirectiveType;
  timestamp: number;
}

export interface TextChunkDirective extends BaseDirective {
  type: "text_chunk";
  content: string;
  model?: "sonnet" | "opus";
}

export interface StreamCompleteDirective extends BaseDirective {
  type: "stream_complete";
  total_tokens?: number;
}

export interface StreamInterruptedDirective extends BaseDirective {
  type: "stream_interrupted";
  retry: boolean;
  reason?: string;
}

export interface PingDirective extends BaseDirective {
  type: "ping";
}

export type Directive =
  | TextChunkDirective
  | StreamCompleteDirective
  | StreamInterruptedDirective
  | PingDirective;

const baseFields = {
  timestamp: z.number(),
};

export const directiveSchema = z.discriminatedUnion("type", [
  z.object({
    ...baseFields,
    type: z.literal("text_chunk"),
    content: z.string(),
    model: z.enum(["sonnet", "opus"]).optional(),
  }),
  z.object({
    ...baseFields,
    type: z.literal("stream_complete"),
    total_tokens: z.number().optional(),
  }),
  z.object({
    ...baseFields,
    type: z.literal("stream_interrupted"),
    retry: z.boolean(),
    reason: z.string().optional(),
  }),
  z.object({
    ...baseFields,
    type: z.literal("ping"),
  }),
]);
