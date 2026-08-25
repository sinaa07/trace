import { Outlet, useLocation } from "react-router-dom";
import { Navbar } from "./Navbar";
import { MVP_NAV_ITEMS, Sidebar } from "./Sidebar";

export function AppLayout() {
  const location = useLocation();

  const navItems = MVP_NAV_ITEMS.map((item) => ({
    ...item,
    active: item.path === location.pathname,
  }));

  return (
    <div className="app-shell">
      <Navbar />
      <div className="app-body">
        <Sidebar items={navItems} />
        <main className="main-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
