import { describe, it, expect, vi, beforeEach } from "vitest";
import { createConversationStream } from "./sse-client";

class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  readonly CONNECTING = 0;
  readonly OPEN = 1;
  readonly CLOSED = 2;
  readyState = 1;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  close() {
    this.readyState = 2;
  }

  simulateMessage(data: string) {
    this.onmessage?.({ data } as MessageEvent);
  }

  simulateError() {
    this.onerror?.(new Event("error"));
  }
}

beforeEach(() => {
  MockEventSource.instances = [];
  vi.stubGlobal("EventSource", MockEventSource);
});

describe("createConversationStream", () => {
  it("parses valid directive and calls onDirective with typed payload", () => {
    const onDirective = vi.fn();
    const onError = vi.fn();
    const onComplete = vi.fn();

    createConversationStream("conv-123", "tenant-abc", {
      onDirective,
      onError,
      onComplete,
    });

    const es = MockEventSource.instances[0];
    es.simulateMessage(
      JSON.stringify({ type: "text", text: "Hello", timestamp: 1000 })
    );

    expect(onDirective).toHaveBeenCalledOnce();
    expect(onDirective).toHaveBeenCalledWith({
      type: "text",
      text: "Hello",
      timestamp: 1000,
    });
    expect(onError).not.toHaveBeenCalled();
    expect(onComplete).not.toHaveBeenCalled();
  });

  it("calls onError on malformed JSON but stream continues receiving messages", () => {
    const onDirective = vi.fn();
    const onError = vi.fn();
    const onComplete = vi.fn();

    createConversationStream("conv-123", "tenant-abc", {
      onDirective,
      onError,
      onComplete,
    });

    const es = MockEventSource.instances[0];

    es.simulateMessage("{ not valid json {{{");

    expect(onError).toHaveBeenCalledOnce();
    expect(onDirective).not.toHaveBeenCalled();
    expect(onComplete).not.toHaveBeenCalled();

    // Stream is still alive: subsequent valid messages are processed normally
    es.simulateMessage(
      JSON.stringify({
        type: "text",
        text: "Still alive",
        timestamp: 2000,
      })
    );

    expect(onDirective).toHaveBeenCalledOnce();
    expect(onDirective).toHaveBeenCalledWith({
      type: "text",
      text: "Still alive",
      timestamp: 2000,
    });
  });
});
