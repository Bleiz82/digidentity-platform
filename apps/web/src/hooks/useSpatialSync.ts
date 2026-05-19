"use client";

import { useState, useCallback, useRef, useEffect } from "react";

export type SceneId = "villa-entrance" | "master-suite" | "infinity-pool";

export interface SpatialMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

export type SpatialStreamState =
  | "idle"
  | "connecting"
  | "streaming"
  | "complete"
  | "error";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const TENANT_ID =
  process.env.NEXT_PUBLIC_DEMO_TENANT_ID ??
  "00000000-0000-0000-0000-000000000001";

/**
 * Manages a conversation stream and extracts spatial_navigate tool_result events
 * to drive the 360° viewer — BIBLE §6.6.
 */
export function useSpatialSync(initialScene: SceneId = "villa-entrance") {
  const [activeScene, setActiveScene] = useState<SceneId>(initialScene);
  const [messages, setMessages] = useState<SpatialMessage[]>([]);
  const [streamState, setStreamState] =
    useState<SpatialStreamState>("idle");
  const [currentStreaming, setCurrentStreaming] = useState("");

  const esRef = useRef<EventSource | null>(null);
  const accRef = useRef("");

  const close = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
  }, []);

  useEffect(() => () => close(), [close]);

  const sendMessage = useCallback(
    (text: string) => {
      close();
      accRef.current = "";
      setCurrentStreaming("");
      setMessages((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: "user", content: text },
      ]);
      setStreamState("connecting");

      const convId = crypto.randomUUID();
      const url =
        `${API_BASE}/api/v1/conversations/${convId}/stream` +
        `?tenant_id=${encodeURIComponent(TENANT_ID)}` +
        `&prompt=${encodeURIComponent(text)}`;

      const es = new EventSource(url);
      esRef.current = es;

      es.onmessage = (event: MessageEvent<string>) => {
        let raw: unknown;
        try {
          raw = JSON.parse(event.data);
        } catch {
          return;
        }
        if (typeof raw !== "object" || raw === null) return;
        const ev = raw as Record<string, unknown>;

        switch (ev.type) {
          case "text": {
            setStreamState("streaming");
            const data = ev.data as Record<string, unknown> | undefined;
            const chunk = (data?.text as string | undefined) ?? "";
            accRef.current += chunk;
            setCurrentStreaming(accRef.current);
            break;
          }
          case "tool_result": {
            const data = ev.data as Record<string, unknown> | undefined;
            if (data?.name === "spatial_navigate") {
              const result = data.result as Record<string, unknown> | undefined;
              const sceneId = result?.scene_id as SceneId | undefined;
              if (sceneId) setActiveScene(sceneId);
            }
            break;
          }
          case "done": {
            const content = accRef.current;
            setMessages((prev) => [
              ...prev,
              {
                id: crypto.randomUUID(),
                role: "assistant",
                content,
              },
            ]);
            accRef.current = "";
            setCurrentStreaming("");
            setStreamState("complete");
            es.close();
            esRef.current = null;
            break;
          }
        }
      };

      es.onerror = () => {
        const content = accRef.current;
        if (content) {
          setMessages((prev) => [
            ...prev,
            { id: crypto.randomUUID(), role: "assistant", content },
          ]);
        }
        accRef.current = "";
        setCurrentStreaming("");
        setStreamState(content ? "complete" : "error");
        esRef.current = null;
      };
    },
    [close],
  );

  return {
    activeScene,
    setActiveScene,
    messages,
    streamState,
    currentStreaming,
    sendMessage,
  };
}
