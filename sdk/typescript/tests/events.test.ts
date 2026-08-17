import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ChronosClient } from "../src/client";

class FakeWebSocket {
  static OPEN = 1;
  public readyState = FakeWebSocket.OPEN;
  public onopen: (() => void) | null = null;
  public onmessage: ((event: { data: string }) => void) | null = null;
  public onclose: (() => void) | null = null;
  public sent: string[] = [];

  constructor(_url: string) {}

  send(payload: string): void {
    this.sent.push(payload);
  }

  emit(eventType: string, payload: Record<string, unknown>): void {
    this.onmessage?.({ data: JSON.stringify({ event_type: eventType, payload }) });
  }
}

describe("ChronosClient contract", () => {
  const originalFetch = globalThis.fetch;
  const originalWebSocket = globalThis.WebSocket;

  beforeEach(() => {
    globalThis.fetch = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => [],
      text: async () => "",
    })) as unknown as typeof fetch;
    Object.defineProperty(globalThis, "WebSocket", {
      configurable: true,
      writable: true,
      value: FakeWebSocket,
    });
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    globalThis.WebSocket = originalWebSocket;
  });

  it("subscribes and dispatches loopback websocket events", () => {
    const client = new ChronosClient({ url: "http://localhost:8420", websocket: true });
    const handler = vi.fn();
    client.on("memory.created", handler);

    const ws = (client as unknown as { ws: FakeWebSocket }).ws;
    expect(ws).toBeTruthy();
    ws.emit("memory.created", { id: "abc" });
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("refuses browser websocket mode when an API key is configured", () => {
    expect(
      () =>
        new ChronosClient({
          url: "https://chronos.example",
          websocket: true,
          apiKey: "secret",
        }),
    ).toThrow(/WebSocket authentication/);
  });

  it("sends delete for forget with API authentication", async () => {
    const client = new ChronosClient({
      url: "https://chronos.example",
      apiKey: "secret",
    });
    await client.forget("abc123", true);

    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/v4/memories/abc123?hard=true");
    expect(init.method).toBe("DELETE");
    expect((init.headers as Record<string, string>)["X-API-Key"]).toBe("secret");
  });

  it("forwards recall context and authenticated JSON headers", async () => {
    const client = new ChronosClient({
      url: "https://chronos.example",
      apiKey: "secret",
    });
    await client.recall({ query: "launch", context: "work", top_k: 7 });

    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("https://chronos.example/api/v4/recall");
    expect((init.headers as Record<string, string>)["X-API-Key"]).toBe("secret");
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
    expect(JSON.parse(String(init.body))).toMatchObject({
      query: "launch",
      context: "work",
      top_k: 7,
    });
  });

  it("bounds server error text exposed by the SDK", async () => {
    globalThis.fetch = vi.fn(async () => ({
      ok: false,
      status: 500,
      json: async () => ({}),
      text: async () => "x".repeat(5000),
    })) as unknown as typeof fetch;
    const client = new ChronosClient({ url: "https://chronos.example" });
    await expect(client.status()).rejects.toThrow(/^HTTP 500: x+/);
  });
});
