export interface Memory {
  id: string;
  content: string;
  summary: string;
  source: string;
  importance: number;
  metadata: Record<string, unknown>;
  created_at: number;
  updated_at: number;
  memory_tier: "working" | "short_term" | "long_term" | "archive";
  modality: string;
  encrypted: boolean;
}

export interface RecallResult {
  memory: Memory;
  score: number;
}

export interface Persona {
  id: string;
  name: string;
  description: string;
  head_checkpoint_id: string | null;
  created_at: number;
  forked_from: string | null;
}

/** REST v4 checkpoint response. parent_id is not emitted by create-checkpoint. */
export interface Checkpoint {
  id: string;
  short_id?: string;
  parent_id?: string | null;
  memory_count: number;
  message: string;
  created_at: number;
}

export interface Entity {
  id: string;
  name: string;
  entity_type: string;
  mention_count: number;
  first_seen_at: number;
  last_seen_at: number;
}

export interface Relationship {
  source_id: string;
  target_id: string;
  rel_type: string;
  weight: number;
  evidence_count: number;
}

export interface ChronosEvent {
  id: number;
  event_type: string;
  payload: Record<string, unknown>;
  persona_id: string;
  created_at: number;
}

export interface ChronosConfig {
  url: string;
  /** Shared CHRONOS API credential used as X-API-Key on HTTP requests. */
  apiKey?: string;
  /** WebSocket is supported for loopback/keyless development only in browser SDK v1. */
  websocket?: boolean;
  timeout?: number;
}

export interface RememberRequest {
  content: string;
  source?: string;
  importance?: number;
  context?: string;
  metadata?: Record<string, unknown>;
}

export interface RecallRequest {
  query: string;
  top_k?: number;
  mode?: "hybrid" | "semantic" | "keyword" | "graph";
  min_importance?: number;
  context?: string;
}

export interface StreamItem {
  content: string;
  source?: string;
  importance?: number;
  metadata?: Record<string, unknown>;
  priority?: number;
  dedup_key?: string;
}

export interface StreamBatchResponse {
  accepted: number;
  total: number;
}

/** Create-view and list-view endpoints return different optional detail fields. */
export interface ViewInfo {
  name: string;
  row_count: number;
  view_id?: string;
  last_refreshed_at?: number;
  refresh_interval_ms?: number;
}

/** Create-snapshot and list-snapshot endpoints return complementary fields. */
export interface SnapshotInfo {
  snapshot_id?: string;
  name: string;
  created_at?: number;
  memory_count?: number;
  size_bytes?: number;
}

export interface RBACPolicy {
  policy_id: string;
  subject_did: string;
  role: string;
  resource: string;
  effect: string;
}
