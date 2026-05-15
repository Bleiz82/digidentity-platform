import { directiveSchema } from "@/types/api";
import type { Directive } from "@/types/api";

export interface StreamOptions {
  onDirective: (directive: Directive) => void;
  onError: (error: Error) => void;
  onComplete: () => void;
}

export interface StreamHandle {
  close: () => void;
}

export function createConversationStream(
  conversationId: string,
  tenantId: string,
  options: StreamOptions
): StreamHandle {
  const { onDirective, onError, onComplete } = options;

  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
  const url = `${baseUrl}/api/v1/conversations/${encodeURIComponent(conversationId)}/stream?tenant_id=${encodeURIComponent(tenantId)}`;
  const es = new EventSource(url);

  es.onmessage = (event: MessageEvent) => {
    let raw: unknown;
    try {
      raw = JSON.parse(event.data as string);
    } catch {
      onError(new Error(`Malformed SSE payload: not valid JSON — "${event.data}"`));
      return;
    }

    const result = directiveSchema.safeParse(raw);
    if (!result.success) {
      onError(new Error(`Invalid directive schema: ${result.error.message}`));
      return;
    }

    const directive = result.data as Directive;

    if (directive.type === "ping") {
      return;
    }

    if (directive.type === "stream_complete") {
      onDirective(directive);
      onComplete();
      es.close();
      return;
    }

    onDirective(directive);
  };

  es.onerror = () => {
    onError(new Error("SSE connection error"));
  };

  return {
    close: () => es.close(),
  };
}
