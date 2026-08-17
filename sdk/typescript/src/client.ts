import type {
  Checkpoint,
  ChronosConfig,
  Memory,
  RBACPolicy,
  RecallRequest,
  RecallResult,
  RememberRequest,
  SnapshotInfo,
  StreamBatchResponse,
  StreamItem,
  ViewInfo,
} from "./types";

export class ChronosClient {
  private readonly url: string;
  private readonly timeout: number;
  private readonly apiKey?: string;
  private ws: WebSocket | null = null;
  private readonly eventHandlers: Map<string, Array<(event: unknown) => void>> = new Map();

  constructor(config: ChronosConfig) {
    this.url = config.url.replace(/\/$/, "");
    this.timeout = config.timeout ?? 30000;
    this.apiKey = config.apiKey;
    if (config.websocket) {
      if (this.apiKey) {
        throw new Error(
          "Browser WebSocket authentication is not supported by SDK v1; disable websocket or use loopback/keyless development",
        );
      }
      this.connectWebSocket();
    }
  }

  async remember(req: RememberRequest): Promise<Memory> {
    return this.post("/api/v4/memories", {
      content: req.content,
      source: req.source ?? "sdk-ts",
      importance: req.importance ?? 0.5,
      context: req.context,
      metadata: req.metadata,
    });
  }

  async recall(req: RecallRequest): Promise<RecallResult[]> {
    return this.post("/api/v4/recall", {
      query: req.query,
      top_k: req.top_k ?? 10,
      mode: req.mode ?? "hybrid",
      min_importance: req.min_importance ?? 0,
      context: req.context,
    });
  }

  async forget(memoryId: string, hard = false): Promise<void> {
    await this.delete(
      `/api/v4/memories/${encodeURIComponent(memoryId)}?hard=${hard ? "true" : "false"}`,
    );
  }

  async checkpoint(message: string): Promise<Checkpoint> {
    return this.post("/api/v4/checkpoints", { message });
  }

  async tql(query: string): Promise<Record<string, unknown>> {
    return this.post("/api/v4/tql", { query });
  }

  async tqlExplain(query: string): Promise<string> {
    const response = await this.post<{ explain: string }>("/api/v4/tql/explain", { query });
    return response.explain;
  }

  async streamBatch(items: StreamItem[]): Promise<StreamBatchResponse> {
    return this.post("/api/v4/stream/batch", { items });
  }

  async streamMetrics(): Promise<Record<string, unknown>> {
    return this.get("/api/v4/stream/metrics");
  }

  async createView(
    name: string,
    tqlQuery: string,
    refreshIntervalMs = 30000,
  ): Promise<ViewInfo> {
    return this.post("/api/v4/views", {
      name,
      tql_query: tqlQuery,
      refresh_interval_ms: refreshIntervalMs,
    });
  }

  async queryView(name: string): Promise<Array<Record<string, unknown>>> {
    return this.get(`/api/v4/views/${encodeURIComponent(name)}`);
  }

  async listViews(): Promise<ViewInfo[]> {
    return this.get("/api/v4/views");
  }

  async refreshView(name: string): Promise<{ refreshed: boolean; row_count: number }> {
    return this.post(`/api/v4/views/${encodeURIComponent(name)}/refresh`, {});
  }

  async createSnapshot(name = ""): Promise<SnapshotInfo> {
    return this.post("/api/v4/snapshots", { name });
  }

  async listSnapshots(): Promise<SnapshotInfo[]> {
    return this.get("/api/v4/snapshots");
  }

  async restoreSnapshot(name: string): Promise<{ restored: boolean; name: string }> {
    return this.post(`/api/v4/snapshots/${encodeURIComponent(name)}/restore`, {});
  }

  async rbacGrant(
    subjectDid: string,
    role: string,
    resource = "repo:*",
  ): Promise<{ policy_id: string; role: string }> {
    return this.post("/api/v4/rbac/grant", {
      subject_did: subjectDid,
      role,
      resource,
    });
  }

  async rbacRevoke(policyId: string): Promise<{ revoked: boolean }> {
    return this.delete(`/api/v4/rbac/policies/${encodeURIComponent(policyId)}`);
  }

  async rbacList(): Promise<RBACPolicy[]> {
    return this.get("/api/v4/rbac/policies");
  }

  async rbacCheck(
    agentDid: string,
    permission: string,
    resource = "repo:*",
  ): Promise<{ allowed: boolean; permission: string }> {
    return this.post("/api/v4/rbac/check", {
      agent_did: agentDid,
      permission,
      resource,
    });
  }

  async status(): Promise<Record<string, unknown>> {
    return this.get("/api/v1/status");
  }

  async health(): Promise<boolean> {
    try {
      await this.get("/api/v1/health");
      return true;
    } catch {
      return false;
    }
  }

  on(eventType: string, handler: (event: unknown) => void): void {
    if (!this.eventHandlers.has(eventType)) {
      this.eventHandlers.set(eventType, []);
    }
    this.eventHandlers.get(eventType)!.push(handler);

    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action: "subscribe", event_types: [eventType] }));
    }
  }

  private connectWebSocket(): void {
    const wsUrl = this.url.replace(/^http/, "ws") + "/api/v4/events/stream";
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      const eventTypes = Array.from(this.eventHandlers.keys());
      this.ws?.send(JSON.stringify({ event_types: eventTypes.length > 0 ? eventTypes : ["*"] }));
    };

    this.ws.onmessage = (message: MessageEvent) => {
      try {
        const data = JSON.parse(message.data as string) as Record<string, unknown>;
        const eventType = String(data.event_type ?? "");
        const handlers = this.eventHandlers.get(eventType) ?? [];
        handlers.forEach((handler) => handler(data));
      } catch {
        // Malformed event frames are ignored instead of crashing the host app.
      }
    };

    this.ws.onclose = () => {
      this.ws = null;
    };
  }

  private headers(json = false): HeadersInit {
    const headers: Record<string, string> = {};
    if (json) {
      headers["Content-Type"] = "application/json";
    }
    if (this.apiKey) {
      headers["X-API-Key"] = this.apiKey;
    }
    return headers;
  }

  private async get<T>(path: string): Promise<T> {
    const response = await fetch(`${this.url}${path}`, {
      headers: this.headers(false),
      signal: AbortSignal.timeout(this.timeout),
    });
    return this.parseResponse<T>(response);
  }

  private async post<T>(path: string, body: unknown): Promise<T> {
    const response = await fetch(`${this.url}${path}`, {
      method: "POST",
      headers: this.headers(true),
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(this.timeout),
    });
    return this.parseResponse<T>(response);
  }

  private async delete<T>(path: string): Promise<T> {
    const response = await fetch(`${this.url}${path}`, {
      method: "DELETE",
      headers: this.headers(false),
      signal: AbortSignal.timeout(this.timeout),
    });
    return this.parseResponse<T>(response);
  }

  private async parseResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
      const body = await response.text();
      throw new Error(`HTTP ${response.status}: ${body.slice(0, 4096)}`);
    }
    return response.json() as Promise<T>;
  }
}
