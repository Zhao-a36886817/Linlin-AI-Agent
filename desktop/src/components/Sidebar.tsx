interface SidebarProps {
  version: string;
}

const navigationItems = [
  { label: "Dashboard", icon: "◈", active: true },
  { label: "Chat", icon: "◉", active: false },
  { label: "Projects", icon: "▣", active: false },
  { label: "Agents", icon: "⌘", active: false },
  { label: "Models", icon: "◇", active: false },
  { label: "Tools", icon: "⚒", active: false },
  { label: "Memory", icon: "◎", active: false },
  { label: "Plugins", icon: "⬡", active: false },
  { label: "Settings", icon: "⚙", active: false },
];

export function Sidebar({ version }: SidebarProps) {
  return (
    <aside className="sidebar">
      <div>
        <p className="sidebar-heading">Workspace</p>

        <nav className="navigation">
          {navigationItems.map((item) => (
            <button
              key={item.label}
              className={`navigation-item ${
                item.active ? "active" : ""
              }`}
              type="button"
              disabled={!item.active}
            >
              <span className="navigation-icon">{item.icon}</span>
              <span>{item.label}</span>

              {!item.active && (
                <span className="coming-soon">Soon</span>
              )}
            </button>
          ))}
        </nav>
      </div>

      <div className="sidebar-footer">
        <span>Linlin Agent</span>
        <strong>v{version}</strong>
      </div>
    </aside>
  );
}