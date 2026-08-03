import type { BackendConnectionStatus } from "../types/api";

interface TopBarProps {
  connectionStatus: BackendConnectionStatus;
}

const statusLabels: Record<BackendConnectionStatus, string> = {
  checking: "Checking",
  online: "Online",
  offline: "Offline",
};

export function TopBar({
  connectionStatus,
}: TopBarProps) {
  return (
    <header className="top-bar">
      <div className="brand">
        <div className="brand-logo">L</div>

        <div className="brand-text">
          <h1>Linlin Agent</h1>
          <p>Multi-Agent AI Desktop Platform</p>
        </div>
      </div>

      <div className="top-bar-actions">
        <div
          className={`backend-badge ${connectionStatus}`}
        >
          <span className="backend-dot" />
          Backend {statusLabels[connectionStatus]}
        </div>

        <button
          className="icon-button"
          type="button"
          title="通知"
          disabled
        >
          ◌
        </button>

        <button
          className="profile-button"
          type="button"
          title="使用者"
        >
          Z
        </button>
      </div>
    </header>
  );
}