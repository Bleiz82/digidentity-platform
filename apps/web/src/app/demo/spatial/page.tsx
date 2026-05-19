"use client";

/**
 * /demo/spatial — 360° tour synchronized with agent conversation.
 * BIBLE §6.6 Spatial Experience v1.
 *
 * Layout: 60% viewer (left) · 40% chat (right).
 * The agent's spatial_navigate tool calls drive the viewer in real time.
 */

import { useEffect, useRef } from "react";
import dynamic from "next/dynamic";
import { useSpatialSync, type SceneId } from "@/hooks/useSpatialSync";
import { StreamStatus } from "@/components/StreamStatus";
import { ChatInput } from "@/components/ChatInput";
import { MessageBubble } from "@/components/MessageBubble";

// PSV needs browser globals — skip SSR
const SpatialViewer = dynamic(
  () =>
    import("@/components/SpatialViewer").then((m) => ({ default: m.SpatialViewer })),
  { ssr: false, loading: () => <div className="w-full h-full bg-gray-900" /> },
);

const SCENES: { id: SceneId; label: string }[] = [
  { id: "villa-entrance", label: "Ingresso" },
  { id: "master-suite", label: "Master Suite" },
  { id: "infinity-pool", label: "Infinity Pool" },
];

const SUGGESTED_PROMPTS = [
  "Mostrami la camera principale",
  "Voglio vedere la piscina",
  "Iniziamo dall'ingresso della villa",
];

export default function SpatialDemoPage() {
  const {
    activeScene,
    setActiveScene,
    messages,
    streamState,
    currentStreaming,
    sendMessage,
  } = useSpatialSync("villa-entrance");

  const scrollAnchorRef = useRef<HTMLDivElement>(null);
  const isStreaming =
    streamState === "connecting" || streamState === "streaming";

  useEffect(() => {
    scrollAnchorRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, currentStreaming]);

  return (
    <div className="flex h-screen bg-gray-950 text-white overflow-hidden">
      {/* ── 360° Viewer (60%) ─────────────────────────────────── */}
      <div className="relative flex-[3] min-w-0">
        <SpatialViewer sceneId={activeScene} className="absolute inset-0" />

        {/* Scene selector overlay */}
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex gap-2 z-10">
          {SCENES.map((s) => (
            <button
              key={s.id}
              onClick={() => setActiveScene(s.id)}
              className={`px-4 py-2 rounded-full text-xs font-medium transition-all backdrop-blur-sm border ${
                activeScene === s.id
                  ? "bg-white/20 border-white/60 text-white"
                  : "bg-black/40 border-white/20 text-white/70 hover:bg-white/10 hover:border-white/40"
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>

        {/* Active scene badge */}
        <div className="absolute top-4 left-4 z-10">
          <span className="bg-black/60 backdrop-blur-sm text-white/80 text-xs px-3 py-1 rounded-full border border-white/10">
            {SCENES.find((s) => s.id === activeScene)?.label ?? activeScene}
          </span>
        </div>
      </div>

      {/* ── Chat panel (40%) ──────────────────────────────────── */}
      <div className="flex-[2] min-w-0 flex flex-col border-l border-gray-800">
        {/* Header */}
        <header className="flex items-center justify-between px-4 py-3 border-b border-gray-800 bg-gray-900/80 backdrop-blur-sm">
          <div>
            <h1 className="text-sm font-semibold">Spatial Experience Demo</h1>
            <p className="text-xs text-gray-500">
              BIBLE §6.6 · agent drives the viewer
            </p>
          </div>
          <StreamStatus state={streamState} />
        </header>

        {/* Messages */}
        <main className="flex-1 overflow-y-auto p-4 space-y-3">
          {messages.length === 0 && streamState === "idle" ? (
            <div className="flex flex-col gap-3 pt-6">
              <p className="text-gray-500 text-sm text-center">
                Chiedi all&apos;agente di guidarti nella villa…
              </p>
              {SUGGESTED_PROMPTS.map((p) => (
                <button
                  key={p}
                  onClick={() => sendMessage(p)}
                  className="text-left px-3 py-2 rounded-lg border border-gray-700 bg-gray-900 text-sm text-gray-300 hover:bg-gray-800 hover:border-gray-600 transition-colors"
                >
                  {p}
                </button>
              ))}
            </div>
          ) : (
            <>
              {messages.map((msg) => (
                <MessageBubble
                  key={msg.id}
                  role={msg.role}
                  content={msg.content}
                />
              ))}
              {currentStreaming && (
                <MessageBubble
                  role="assistant"
                  content={currentStreaming}
                  streaming
                />
              )}
              {streamState === "connecting" && !currentStreaming && (
                <MessageBubble role="assistant" content="" streaming />
              )}
            </>
          )}
          <div ref={scrollAnchorRef} />
        </main>

        {/* Input */}
        <footer className="border-t border-gray-800 p-3 bg-gray-900/80">
          <ChatInput onSubmit={sendMessage} disabled={isStreaming} />
        </footer>
      </div>
    </div>
  );
}
