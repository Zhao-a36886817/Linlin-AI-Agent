import { useCallback, useEffect, useState } from "react";

import "./App.css";

import { RuntimePanel } from "./components/RuntimePanel";
import { Sidebar } from "./components/Sidebar";
import { TopBar } from "./components/TopBar";
import { DashboardPage } from "./pages/DashboardPage";
import { api } from "./services/api";

import type {
  AgentStatusResponse,
  BackendConnectionStatus,
  HealthResponse,
  SystemInfoResponse,
} from "./types/api";

function App() {
  const [connectionStatus, setConnectionStatus] =
    useState<BackendConnectionStatus>("checking");

  const [health, setHealth] =
    useState<HealthResponse | null>(null);

  const [systemInfo, setSystemInfo] =
    useState<SystemInfoResponse | null>(null);

  const [agentStatus, setAgentStatus] =
    useState<AgentStatusResponse | null>(null);

  const [lastError, setLastError] =
    useState<string | null>(null);

  const refreshDashboard = useCallback(async () => {
    setConnectionStatus("checking");

    try {
      const data = await api.getDashboardData();

      setHealth(data.health);
      setSystemInfo(data.system);
      setAgentStatus(data.agents);
      setConnectionStatus("online");
      setLastError(null);
    } catch (error) {
      setConnectionStatus("offline");

      setLastError(
        error instanceof Error
          ? error.message
          : "Unknown backend error",
      );
    }
  }, []);

  useEffect(() => {
    void refreshDashboard();

    const intervalId = window.setInterval(() => {
      void refreshDashboard();
    }, 10000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [refreshDashboard]);

  return (
    <main className="app-shell">
      <TopBar connectionStatus={connectionStatus} />

      <div className="workspace-layout">
        <Sidebar version={health?.version ?? "0.1.0"} />

        <DashboardPage
          connectionStatus={connectionStatus}
          health={health}
          systemInfo={systemInfo}
          agentStatus={agentStatus}
          lastError={lastError}
          onRefresh={() => void refreshDashboard()}
        />

        <RuntimePanel
          agentStatus={agentStatus}
          systemInfo={systemInfo}
        />
      </div>

      <footer className="bottom-bar">
        <span>
          Backend: http://127.0.0.1:8000
        </span>

        <span>
          {systemInfo?.platform ??
            "Waiting for backend information"}
        </span>
      </footer>
    </main>
  );
}

export default App;