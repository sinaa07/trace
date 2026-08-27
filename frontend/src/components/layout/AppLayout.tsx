import { Outlet, useLocation } from "react-router-dom";
import { Navbar } from "./Navbar";
import { Sidebar, navItemsForPath } from "./Sidebar";

export function AppLayout() {
  const location = useLocation();
  const navItems = navItemsForPath(location.pathname);

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
