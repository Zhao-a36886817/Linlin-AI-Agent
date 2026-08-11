export interface ChatMessage {
  role: "user" | "assistant" | "tool";
  content: string;
}

export interface ChatRequest {
  provider: string;
  model: string;
  tools_enabled: boolean;
  messages: ChatMessage[];
  options?: {
    temperature?: number;
    max_tokens?: number;
    think?: boolean;
  };
}

export interface ChatStreamEvent extends ChatResponse {
  done: boolean;
}

export interface ModelInfo {
  provider: string;
  provider_label?: string | null;
  name: string;
  local: boolean;
  family: string | null;
  parameter_size: string | null;
  quantization: string | null;
  capabilities: string[];
}

export interface CloudProviderInfo {
  id: string;
  name: string;
  kind: string;
  cost_class: "LOCAL_FREE" | "FREE_TIER" | "PAID" | "UNKNOWN";
  base_url: string | null;
  has_api_key: boolean;
  default_model: string | null;
  enabled: boolean;
}

export interface CloudProviderList {
  items: CloudProviderInfo[];
  total: number;
  enabled: number;
}

export interface CloudConnectResult {
  provider: CloudProviderInfo;
  runtime_name: string;
  detected_kind: string;
  credential_persistent: boolean;
  models: Array<{ name: string; capabilities?: string[] }>;
}

export interface CodeProposal {
  id: string;
  provider: string;
  model: string;
  instruction: string;
  target_path: string;
  summary: string;
  content: string;
  diff: string;
  status: "pending" | "applied" | "discarded";
  created_at: string;
  applied_at?: string;
  warnings: string[];
}

export interface TrainingMetric {
  step: number;
  train_loss?: number | null;
  valid_loss?: number | null;
}

export interface TrainingJob {
  id: string;
  conversation_id: string;
  engine: "openai_compatible" | "local_lora";
  provider: string;
  provider_label: string;
  model: string;
  provider_job_id: string;
  status: "validating" | "uploading" | "queued" | "running" | "succeeded" | "failed" | "cancelled" | "unknown";
  examples: number;
  created_at: string;
  updated_at: string;
  trained_model?: string | null;
  error?: string | null;
  metrics: TrainingMetric[];
}

export interface TrainingModel {
  engine: "openai_compatible" | "local_lora";
  provider: string;
  provider_label: string;
  model: string;
  local: boolean;
  size_bytes?: number | null;
}

export interface TrainingCapabilities {
  models: TrainingModel[];
  local: { available: boolean; engine: "local_lora"; reason: string };
  polling_interval_seconds: number;
  max_active_jobs: number;
}

export interface ModelListResponse {
  items: ModelInfo[];
  total: number;
}

export interface ChatResponse {
  provider: string;
  model: string;
  role: string;
  content: string;
  thinking?: string | null;
  tool_calls?: unknown[];
  done: boolean;
}

export type RuntimeKey = "memory" | "rag" | "mcp" | "orchestration" | "scheduler";

export interface RuntimeFeature {
  key: RuntimeKey;
  label: string;
  enabled: boolean;
  configured: boolean;
  status: "ready" | "disabled" | "setup_required";
  summary: string;
  safety: string;
}

export interface RuntimeOverview {
  local_first: boolean;
  features: RuntimeFeature[];
}

export interface RagResult {
  text: string;
  score: number;
  citation: { source: string; start: number; end: number };
  untrusted_instructions: boolean;
}

export interface McpToolDefinition {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
}

export interface OrchestrationRun {
  id: string;
  provider: string;
  model: string;
  task: string;
  status: "pending" | "running" | "completed" | "cancelled" | "failed";
  output: { analysis: string; review: string } | null;
  error: string | null;
}

export interface ScheduledJob {
  id: string;
  action: string;
  arguments: Record<string, unknown>;
  run_at: string;
  status: "scheduled" | "completed" | "cancelled" | "failed";
  attempts: number;
  max_attempts: number;
}

export interface SchedulerState {
  enabled: boolean;
  jobs: ScheduledJob[];
  audit: Array<{ job_id: string; event: string; occurred_at: string }>;
  results: Record<string, { status: string; content: string | null; provider?: string; model?: string }>;
}

export interface MemoryRecord {
  id: string;
  owner_id: string;
  session_id: string | null;
  content: string;
  created_at: string;
  expires_at: string;
}
