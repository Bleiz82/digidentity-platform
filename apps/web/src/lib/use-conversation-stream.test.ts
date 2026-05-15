import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useConversationStream } from "./use-conversation-stream";
import type { StreamOptions } from "./sse-client";

const mockClose = vi.fn();
let capturedOptions: StreamOptions | null = null;

vi.mock("@/lib/sse-client", () => ({
  createConversationStream: vi.fn(
    (_convId: string, _tenantId: string, options: StreamOptions) => {
      capturedOptions = options;
      return { close: mockClose };
    }
  ),
}));

beforeEach(() => {
  vi.clearAllMocks();
  capturedOptions = null;
});

describe("useConversationStream", () => {
  it("sends user message and enters streaming state on first text_chunk", () => {
    const { result } = renderHook(() => useConversationStream());

    act(() => {
      result.current.sendMessage("Test message");
    });

    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0].role).toBe("user");
    expect(result.current.messages[0].content).toBe("Test message");
    expect(result.current.streamState).toBe("connecting");

    act(() => {
      capturedOptions?.onDirective({
        type: "text_chunk",
        content: "Ciao",
        timestamp: 1000,
      });
    });

    expect(result.current.streamState).toBe("streaming");
  });

  it("accumulates text_chunk directives into currentStreaming", () => {
    const { result } = renderHook(() => useConversationStream());

    act(() => {
      result.current.sendMessage("Ciao");
    });

    act(() => {
      capturedOptions?.onDirective({ type: "text_chunk", content: "Cer", timestamp: 1000 });
      capturedOptions?.onDirective({ type: "text_chunk", content: "to", timestamp: 1001 });
      capturedOptions?.onDirective({ type: "text_chunk", content: "!", timestamp: 1002 });
    });

    expect(result.current.currentStreaming).toBe("Certo!");
  });

  it("finalizes assistant message on stream_complete and clears currentStreaming", () => {
    const { result } = renderHook(() => useConversationStream());

    act(() => {
      result.current.sendMessage("Ciao");
    });

    act(() => {
      capturedOptions?.onDirective({ type: "text_chunk", content: "Risposta", timestamp: 1000 });
    });

    act(() => {
      capturedOptions?.onComplete();
    });

    expect(result.current.currentStreaming).toBe("");
    expect(result.current.streamState).toBe("complete");
    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[1].role).toBe("assistant");
    expect(result.current.messages[1].content).toBe("Risposta");
  });
});
