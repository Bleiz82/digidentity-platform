import { useState, useCallback, useRef, useEffect } from "react";
import { createConversationStream, type StreamHandle } from "@/lib/sse-client";
import type { Directive } from "@/types/api";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
}

export type StreamState =
  | "idle"
  | "connecting"
  | "streaming"
  | "error"
  | "complete";

export function useConversationStream() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [streamState, setStreamState] = useState<StreamState>("idle");
  const [currentStreaming, setCurrentStreaming] = useState<string>("");

  const streamRef = useRef<StreamHandle | null>(null);
  // Ref to avoid stale closure when finalizing the assistant message
  const accumulatedRef = useRef<string>("");

  const cancel = useCallback(() => {
    streamRef.current?.close();
    streamRef.current = null;
    accumulatedRef.current = "";
    setCurrentStreaming("");
    setStreamState("idle");
  }, []);

  const sendMessage = useCallback((text: string) => {
    streamRef.current?.close();
    streamRef.current = null;
    accumulatedRef.current = "";
    setCurrentStreaming("");

    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role: "user", content: text },
    ]);
    setStreamState("connecting");

    const conversationId = crypto.randomUUID();
    const tenantId =
      process.env.NEXT_PUBLIC_DEMO_TENANT_ID ??
      "00000000-0000-0000-0000-000000000001";

    const handle = createConversationStream(conversationId, tenantId, {
      onDirective: (directive: Directive) => {
        if (directive.type === "text") {
          setStreamState("streaming");
          accumulatedRef.current += directive.text;
          setCurrentStreaming(accumulatedRef.current);
        } else if (directive.type === "stream_interrupted") {
          setStreamState("error");
        }
        // stream_complete is handled exclusively by onComplete
      },
      onError: (error: Error) => {
        console.warn("[SSE]", error.message);
        setStreamState("error");
      },
      onComplete: () => {
        // Capture before clearing — functional updater executes during React flush,
        // after accumulatedRef.current would already be reset.
        const content = accumulatedRef.current;
        setMessages((prev) => [
          ...prev,
          { id: crypto.randomUUID(), role: "assistant", content },
        ]);
        accumulatedRef.current = "";
        setCurrentStreaming("");
        setStreamState("complete");
        streamRef.current = null;
      },
    });

    streamRef.current = handle;
  }, []);

  // Cleanup on unmount — no memory leak from open EventSource
  useEffect(() => {
    return () => {
      streamRef.current?.close();
    };
  }, []);

  return { messages, streamState, currentStreaming, sendMessage, cancel };
}
