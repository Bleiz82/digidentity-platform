"use client";

import { useEffect, useRef } from "react";
import { useConversationStream } from "@/lib/use-conversation-stream";
import { ChatInput } from "@/components/ChatInput";
import { MessageBubble } from "@/components/MessageBubble";
import { StreamStatus } from "@/components/StreamStatus";

const SUGGESTED_PROMPTS = [
  "Cerco una villa con vista mare in Costa Smeralda",
  "Quali sono le caratteristiche delle residenze di lusso?",
  "Investimento immobiliare per famiglia internazionale",
];

export function ConversationUI() {
  const { messages, streamState, currentStreaming, sendMessage } =
    useConversationStream();

  const scrollAnchorRef = useRef<HTMLDivElement>(null);
  const isStreaming = streamState === "connecting" || streamState === "streaming";

  // Auto-scroll to bottom on new content
  useEffect(() => {
    scrollAnchorRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, currentStreaming]);

  const lastUserMessage = [...messages]
    .reverse()
    .find((m) => m.role === "user")?.content;

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex flex-col">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-4 py-3">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
              DigIdentity — Real Estate Luxury Demo
            </h1>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Phase 2 streaming preview
            </p>
          </div>
          <StreamStatus state={streamState} />
        </div>
      </header>

      {/* Message area */}
      <main className="flex-1 overflow-y-auto max-h-[70vh]">
        <div className="max-w-3xl mx-auto px-4 py-6 space-y-4">
          {messages.length === 0 && streamState === "idle" ? (
            /* Empty state */
            <div className="flex flex-col items-center gap-6 pt-10">
              <p className="text-gray-500 dark:text-gray-400 text-sm text-center">
                Inizia una conversazione sui nostri immobili di lusso…
              </p>
              <div className="flex flex-col gap-2 w-full max-w-md">
                {SUGGESTED_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => sendMessage(prompt)}
                    className="text-left px-4 py-3 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 hover:border-blue-300 dark:hover:border-blue-600 transition-colors"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
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

              {/* In-progress streaming bubble */}
              {currentStreaming && (
                <MessageBubble
                  role="assistant"
                  content={currentStreaming}
                  streaming
                />
              )}

              {/* Connecting placeholder */}
              {streamState === "connecting" && !currentStreaming && (
                <MessageBubble
                  role="assistant"
                  content=""
                  streaming
                />
              )}

              {/* Error retry */}
              {streamState === "error" && lastUserMessage && (
                <div className="flex justify-center">
                  <button
                    onClick={() => sendMessage(lastUserMessage)}
                    className="px-4 py-2 text-sm text-red-600 dark:text-red-400 border border-red-300 dark:border-red-700 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/30 transition-colors"
                  >
                    Riprova
                  </button>
                </div>
              )}
            </>
          )}

          <div ref={scrollAnchorRef} />
        </div>
      </main>

      {/* Input */}
      <footer className="sticky bottom-0 bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 px-4 py-3">
        <div className="max-w-3xl mx-auto">
          <ChatInput onSubmit={sendMessage} disabled={isStreaming} />
        </div>
      </footer>
    </div>
  );
}
