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
  { label: "Cases", path: "/cases" },
  { label: "Case Overview", path: "/overview" },
  { label: "Evidence Explorer", path: "/evidence" },
  { label: "Timeline", path: "/timeline" },
  { label: "Anomalies", path: "/anomalies" },
  { label: "Conflicts", path: "/conflicts" },
  { label: "Findings", path: "/findings" },
  { label: "Hypotheses", path: "/hypotheses" },
  { label: "Causal Graph", path: "/graph" },
  { label: "Evidence Gaps", path: "/gaps" },
  { label: "Report", disabled: true, badge: "Soon" },
  { label: "Audit Trail", path: "/audit" },
];

export function navItemsForPath(pathname: string): NavItem[] {
  return MVP_NAV_ITEMS.map((item) => {
    if (!item.path) return { ...item, active: false };
    if (item.path === "/") {
      return { ...item, active: pathname === "/" };
    }
    return { ...item, active: pathname === item.path || pathname.startsWith(`${item.path}/`) };
  });
}
