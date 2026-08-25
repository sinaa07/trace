import { Link } from "react-router-dom";

export interface NavItem {
  label: string;
  path?: string;
  active?: boolean;
  disabled?: boolean;
  badge?: string;
}

interface SidebarProps {
  items: NavItem[];
  sectionLabel?: string;
}

export function Sidebar({ items, sectionLabel = "Investigation Workspace" }: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="sidebar-section">
        <div className="sidebar-label">{sectionLabel}</div>
        <nav>
          {items.map((item) => {
            const className = [
              "sidebar-link",
              item.active ? "active" : "",
              item.disabled ? "disabled" : "",
            ]
              .filter(Boolean)
              .join(" ");

            if (item.disabled || !item.path) {
              return (
                <span key={item.label} className={className} aria-disabled="true">
                  {item.label}
                  {item.badge && <span className="sidebar-badge">{item.badge}</span>}
                </span>
              );
            }

            return (
              <Link key={item.label} to={item.path} className={className}>
                {item.label}
                {item.badge && <span className="sidebar-badge">{item.badge}</span>}
              </Link>
            );
          })}
        </nav>
      </div>
    </aside>
  );
}

export const MVP_NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", path: "/" },
  { label: "Case Ingestion", path: "/ingestion" },
  { label: "Cases", disabled: true, badge: "Soon" },
  { label: "Case Overview", disabled: true, badge: "Soon" },
  { label: "Evidence Explorer", disabled: true, badge: "Soon" },
  { label: "Timeline", disabled: true, badge: "Soon" },
  { label: "Anomalies", disabled: true, badge: "Soon" },
  { label: "Conflicts", disabled: true, badge: "Soon" },
  { label: "Hypotheses", disabled: true, badge: "Soon" },
  { label: "Causal Graph", disabled: true, badge: "Soon" },
  { label: "Evidence Gaps", disabled: true, badge: "Soon" },
  { label: "Findings", disabled: true, badge: "Soon" },
  { label: "Report", disabled: true, badge: "Soon" },
  { label: "Audit Trail", disabled: true, badge: "Soon" },
];
