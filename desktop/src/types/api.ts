export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  environment: string;
  timestamp: string;
}

export interface SystemInfoResponse {
  app_name: string;
  app_version: string;
  environment: string;
  python_version: string;
  platform: string;
  architecture: string;
  hostname: string;
  cpu_count: number;
  memory_total_gb: number;
}

export interface AgentStatusResponse {
  runtime_status: string;
  configured_models: number;
  active_agents: number;
  max_parallel_agents: number;
  current_task_id: string | null;
}

export interface DashboardData {
  health: HealthResponse;
  system: SystemInfoResponse;
  agents: AgentStatusResponse;
}

export type BackendConnectionStatus =
  | "checking"
  | "online"
  | "offline";