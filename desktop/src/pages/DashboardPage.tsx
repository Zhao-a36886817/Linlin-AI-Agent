import { StatusCard } from "../components/StatusCard";

import type {
  AgentStatusResponse,
  BackendConnectionStatus,
  HealthResponse,
  SystemInfoResponse,
} from "../types/api";

interface DashboardPageProps {
  connectionStatus: BackendConnectionStatus;
  health: HealthResponse | null;
  systemInfo: SystemInfoResponse | null;
  agentStatus: AgentStatusResponse | null;
  lastError: string | null;
  onRefresh: () => void;
}

const connectionLabels: Record<
  BackendConnectionStatus,
  string
> = {
  checking: "Checking",
  online: "Online",
  offline: "Offline",
};

export function DashboardPage({
  connectionStatus,
  health,
  systemInfo,
  agentStatus,
  lastError,
  onRefresh,
}: DashboardPageProps) {
  return (
    <section className="dashboard-page">
      <article className="hero-card">
        <div>
          <span className="eyebrow">
            LINLIN AGENT · FOUNDATION
          </span>

          <h2>多模型自動代理工作台</h2>

          <p>
            FastAPI、React、TypeScript 與 Tauri
            已完成基礎連線。接下來將加入雲端模型 Provider、
            多 Agent Runtime、Workspace 與工具執行系統。
          </p>
        </div>

        <button
          className="primary-button"
          type="button"
          onClick={onRefresh}
        >
          重新檢查
        </button>
      </article>

      {connectionStatus === "offline" && (
        <article className="error-banner">
          <div>
            <strong>無法連接 FastAPI Backend</strong>
            <span>{lastError ?? "Unknown connection error"}</span>
          </div>

          <code>
            F:\Linlin-Agent\scripts\start-backend.ps1
          </code>
        </article>
      )}

      <section className="status-grid">
        <StatusCard
          title="Backend"
          value={connectionLabels[connectionStatus]}
          description={health?.environment ?? "development"}
          indicator={
            connectionStatus === "online"
              ? "success"
              : connectionStatus === "checking"
                ? "warning"
                : "neutral"
          }
        />

        <StatusCard
          title="Agent Runtime"
          value={agentStatus?.runtime_status ?? "Unknown"}
          description={`${agentStatus?.active_agents ?? 0} active agents`}
          indicator="success"
        />

        <StatusCard
          title="Configured Models"
          value={agentStatus?.configured_models ?? 0}
          description={`Maximum ${
            agentStatus?.max_parallel_agents ?? 4
          } parallel`}
        />

        <StatusCard
          title="System Memory"
          value={
            systemInfo
              ? `${systemInfo.memory_total_gb} GB`
              : "--"
          }
          description={`${systemInfo?.cpu_count ?? "--"} logical processors`}
        />
      </section>

      <section className="dashboard-columns">
        <article className="panel-card">
          <div className="panel-title-row">
            <h3>Backend Information</h3>
            <span className="panel-tag">LOCAL</span>
          </div>

          <dl className="information-list">
            <div>
              <dt>Application</dt>
              <dd>{systemInfo?.app_name ?? "--"}</dd>
            </div>

            <div>
              <dt>Version</dt>
              <dd>{systemInfo?.app_version ?? "--"}</dd>
            </div>

            <div>
              <dt>Python</dt>
              <dd>{systemInfo?.python_version ?? "--"}</dd>
            </div>

            <div>
              <dt>Environment</dt>
              <dd>{systemInfo?.environment ?? "--"}</dd>
            </div>

            <div>
              <dt>Hostname</dt>
              <dd>{systemInfo?.hostname ?? "--"}</dd>
            </div>

            <div>
              <dt>Platform</dt>
              <dd>{systemInfo?.platform ?? "--"}</dd>
            </div>
          </dl>
        </article>

        <article className="panel-card">
          <div className="panel-title-row">
            <h3>Development Progress</h3>
            <span className="panel-tag">v0.1</span>
          </div>

          <ul className="progress-list">
            <li className="complete">
              <span className="progress-dot" />
              Anaconda isolated environment
            </li>

            <li className="complete">
              <span className="progress-dot" />
              FastAPI Backend
            </li>

            <li className="complete">
              <span className="progress-dot" />
              React TypeScript UI
            </li>

            <li className="complete">
              <span className="progress-dot" />
              Tauri Desktop Runtime
            </li>

            <li className="complete">
              <span className="progress-dot" />
              Backend Health API
            </li>

            <li>
              <span className="progress-dot" />
              Cloud Model Provider Manager
            </li>

            <li>
              <span className="progress-dot" />
              Multi-Agent Runtime
            </li>
          </ul>
        </article>
      </section>
    </section>
  );
}
