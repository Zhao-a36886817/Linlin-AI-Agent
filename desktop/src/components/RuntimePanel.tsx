import type {
  AgentStatusResponse,
  SystemInfoResponse,
} from "../types/api";

interface RuntimePanelProps {
  agentStatus: AgentStatusResponse | null;
  systemInfo: SystemInfoResponse | null;
}

export function RuntimePanel({
  agentStatus,
  systemInfo,
}: RuntimePanelProps) {
  return (
    <aside className="runtime-panel">
      <div className="runtime-header">
        <p className="panel-heading">Runtime</p>
        <span className="live-label">LIVE</span>
      </div>

      <div className="runtime-section">
        <div className="runtime-row">
          <span>Status</span>
          <strong>
            {agentStatus?.runtime_status ?? "Unknown"}
          </strong>
        </div>

        <div className="runtime-row">
          <span>Active Agents</span>
          <strong>{agentStatus?.active_agents ?? 0}</strong>
        </div>

        <div className="runtime-row">
          <span>Models</span>
          <strong>
            {agentStatus?.configured_models ?? 0}
          </strong>
        </div>

        <div className="runtime-row">
          <span>Parallel Limit</span>
          <strong>
            {agentStatus?.max_parallel_agents ?? 4}
          </strong>
        </div>

        <div className="runtime-row">
          <span>Current Task</span>
          <strong>
            {agentStatus?.current_task_id ?? "None"}
          </strong>
        </div>
      </div>

      <div className="runtime-section">
        <p className="panel-heading">System</p>

        <div className="runtime-row">
          <span>Architecture</span>
          <strong>{systemInfo?.architecture ?? "--"}</strong>
        </div>

        <div className="runtime-row">
          <span>CPU Threads</span>
          <strong>{systemInfo?.cpu_count ?? "--"}</strong>
        </div>

        <div className="runtime-row">
          <span>Memory</span>
          <strong>
            {systemInfo
              ? `${systemInfo.memory_total_gb} GB`
              : "--"}
          </strong>
        </div>
      </div>
    </aside>
  );
}