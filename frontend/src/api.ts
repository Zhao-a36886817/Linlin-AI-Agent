import type {
  ChatRequest,
  ChatResponse,
  CloudConnectResult,
  CloudProviderList,
  CodeProposal,
  MemoryRecord,
  ModelListResponse,
  McpToolDefinition,
  OrchestrationRun,
  RagResult,
  RuntimeFeature,
  RuntimeOverview,
  SchedulerState,
  TrainingCapabilities,
  TrainingJob,
} from "./types";
import type { ChatStreamEvent } from "./types";

const API_URL = (import.meta.env.VITE_API_BASE_URL ?? "/api").replace(/\/$/, "");
const LOCAL_OWNER = "local-owner";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(typeof body.detail === "string" ? body.detail : "Request failed.");
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export function chat(payload: ChatRequest): Promise<ChatResponse> {
  return request("/chat", { method: "POST", body: JSON.stringify(payload) });
}

export function listModels(includeCloud = false): Promise<ModelListResponse> {
  return request(includeCloud ? "/models?include_cloud=true" : "/models?local_only=true");
}

export function listCloudProviders(): Promise<CloudProviderList> {
  return request("/providers");
}

export function connectCloudProvider(payload: {
  name: string;
  base_url: string;
  api_key?: string;
  credential_env?: string;
  kind?: string;
  consent: boolean;
}): Promise<CloudConnectResult> {
  return request("/providers/connect", { method: "POST", body: JSON.stringify(payload) });
}

export function discoverCloudProvider(providerId: string): Promise<{ runtime_name: string; models: Array<{ name: string }> }> {
  return request(`/providers/${providerId}/discover`, {
    method: "POST",
    body: JSON.stringify({ consent: true }),
  });
}

export function deleteCloudProvider(providerId: string): Promise<void> {
  return request(`/providers/${providerId}`, { method: "DELETE" });
}

export function createCodeProposal(payload: {
  provider: string;
  model: string;
  instruction: string;
  target_path: string;
  context_paths: string[];
  cloud_consent: boolean;
}): Promise<CodeProposal> {
  return request("/code-generation/proposals", { method: "POST", body: JSON.stringify(payload) });
}

export function listCodeProposals(): Promise<CodeProposal[]> {
  return request("/code-generation/proposals");
}

export function applyCodeProposal(proposalId: string): Promise<CodeProposal> {
  return request(`/code-generation/proposals/${proposalId}/apply`, {
    method: "POST",
    body: JSON.stringify({ confirmation: "APPLY CODE", consent: true }),
  });
}

export function discardCodeProposal(proposalId: string): Promise<{ discarded: boolean }> {
  return request(`/code-generation/proposals/${proposalId}`, { method: "DELETE" });
}

export function getTrainingCapabilities(): Promise<TrainingCapabilities> {
  return request("/training/capabilities");
}

export function createTrainingJob(payload: {
  conversation_id: string;
  provider: string;
  model: string;
  messages: Array<{ role: "user" | "assistant"; content: string }>;
  engine: "openai_compatible" | "local_lora";
  cloud_consent: boolean;
  local_consent: boolean;
  max_steps: number;
}): Promise<TrainingJob> {
  return request("/training/jobs", { method: "POST", body: JSON.stringify(payload) });
}

export function listTrainingJobs(conversationId: string): Promise<TrainingJob[]> {
  return request(`/training/jobs?conversation_id=${encodeURIComponent(conversationId)}`);
}

export function cancelTrainingJob(jobId: string, conversationId: string): Promise<TrainingJob> {
  return request(`/training/jobs/${jobId}/cancel?conversation_id=${encodeURIComponent(conversationId)}`, {
    method: "POST",
  });
}

export async function streamChat(
  payload: ChatRequest,
  onEvent: (event: ChatStreamEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const response = await fetch(`${API_URL}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(payload),
    signal,
  });
  if (!response.ok || !response.body) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(typeof body.detail === "string" ? body.detail : "無法建立串流連線。");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, "\n");
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      const eventName = block.split("\n").find((line) => line.startsWith("event:"))?.slice(6).trim();
      const data = block.split("\n").filter((line) => line.startsWith("data:")).map((line) => line.slice(5).trim()).join("\n");
      if (!data) continue;
      const parsed = JSON.parse(data) as ChatStreamEvent | { detail: string };
      if (eventName === "error" && "detail" in parsed) throw new Error(parsed.detail);
      onEvent(parsed as ChatStreamEvent);
    }
    if (done) break;
  }
}

export function getRuntimeOverview(): Promise<RuntimeOverview> {
  return request("/runtime-control");
}

export function setMemoryEnabled(enabled: boolean): Promise<RuntimeFeature> {
  return request("/runtime-control/memory/enabled", {
    method: "PUT",
    body: JSON.stringify({
      enabled,
      confirmation: enabled ? "ENABLE MEMORY" : "DISABLE MEMORY",
    }),
  });
}

function memoryPath(sessionId: string): string {
  const query = sessionId.trim() ? `?session_id=${encodeURIComponent(sessionId.trim())}` : "";
  return `/runtime-control/memory/records${query}`;
}

export function listMemory(sessionId: string): Promise<MemoryRecord[]> {
  return request(memoryPath(sessionId), { headers: { "X-Linlin-Owner": LOCAL_OWNER } });
}

export function createMemory(content: string, sessionId: string): Promise<MemoryRecord> {
  return request("/runtime-control/memory/records", {
    method: "POST",
    headers: { "X-Linlin-Owner": LOCAL_OWNER },
    body: JSON.stringify({ content, session_id: sessionId.trim() || null, consent: true }),
  });
}

export function deleteMemory(recordId: string, sessionId: string): Promise<void> {
  return request(`${memoryPath(sessionId).replace("/records", `/records/${recordId}`)}`, {
    method: "DELETE",
    headers: { "X-Linlin-Owner": LOCAL_OWNER },
  });
}

export function configureRag(enabled: boolean, provider: string, model: string): Promise<unknown> {
  return request("/advanced-runtime/rag", {
    method: "PUT",
    body: JSON.stringify({ enabled, provider, model }),
  });
}

export function ingestRag(path: string): Promise<{ added: number; chunks: number }> {
  return request("/advanced-runtime/rag/ingest", {
    method: "POST",
    body: JSON.stringify({ path, consent: true }),
  });
}

export function searchRag(query: string): Promise<RagResult[]> {
  return request("/advanced-runtime/rag/search", {
    method: "POST",
    body: JSON.stringify({ query, limit: 5 }),
  });
}

export function connectMcp(serverId: string, endpoint: string): Promise<{ connected: boolean; tools: McpToolDefinition[] }> {
  return request("/advanced-runtime/mcp/connect", {
    method: "POST",
    body: JSON.stringify({ server_id: serverId, endpoint, consent: true }),
  });
}

export function disconnectMcp(): Promise<void> {
  return request("/advanced-runtime/mcp", { method: "DELETE" });
}

export function invokeMcp(name: string, arguments_: Record<string, unknown>): Promise<Record<string, unknown>> {
  return request("/advanced-runtime/mcp/invoke", {
    method: "POST",
    body: JSON.stringify({ name, arguments: arguments_ }),
  });
}

export function startOrchestration(provider: string, model: string, task: string): Promise<OrchestrationRun> {
  return request("/advanced-runtime/orchestration/runs", {
    method: "POST",
    body: JSON.stringify({ provider, model, task, iterations: 4, cost_units: 4096 }),
  });
}

export function listOrchestration(): Promise<OrchestrationRun[]> {
  return request("/advanced-runtime/orchestration/runs");
}

export function cancelOrchestration(runId: string): Promise<{ cancelled: boolean }> {
  return request(`/advanced-runtime/orchestration/runs/${runId}`, { method: "DELETE" });
}

export function setSchedulerEnabled(enabled: boolean): Promise<SchedulerState> {
  return request("/advanced-runtime/scheduler", {
    method: "PUT",
    body: JSON.stringify({
      enabled,
      confirmation: enabled ? "ENABLE SCHEDULER" : "DISABLE SCHEDULER",
    }),
  });
}

export function getSchedulerState(): Promise<SchedulerState> {
  return request("/advanced-runtime/scheduler/jobs");
}

export function scheduleChat(provider: string, model: string, prompt: string, runAt: string): Promise<unknown> {
  return request("/advanced-runtime/scheduler/jobs", {
    method: "POST",
    body: JSON.stringify({ provider, model, prompt, run_at: runAt, consent: true }),
  });
}

export function cancelScheduledJob(jobId: string): Promise<{ cancelled: boolean }> {
  return request(`/advanced-runtime/scheduler/jobs/${jobId}`, { method: "DELETE" });
}
