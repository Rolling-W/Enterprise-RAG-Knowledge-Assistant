import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Icon } from "./Icon";

export function AppLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const { session, signOut } = useAuth();
  const { pathname } = useLocation();
  const user = session!.user;
  const initials = user.name
    .split(" ")
    .map((part) => part[0])
    .join("");
  return (
    <div className={`app-layout ${collapsed ? "sidebar-collapsed" : ""}`}>
      <aside className="sidebar" id="app-sidebar">
        <button
          className="sidebar-toggle"
          type="button"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-expanded={!collapsed}
          aria-controls="app-sidebar"
          onClick={() => setCollapsed((value) => !value)}
        >
          <Icon name="chevron" size={16} />
        </button>
        <NavLink
          className="brand"
          to="/assistant"
          aria-label="Enterprise RAG home"
          title={collapsed ? "Enterprise RAG" : undefined}
        >
          <span className="brand-symbol">
            <Icon name="sparkles" size={24} />
          </span>
          <span className="sidebar-text">
            Enterprise RAG<small>KNOWLEDGE ASSISTANT</small>
          </span>
        </NavLink>
        <div className="nav-label">WORKSPACE</div>
        <nav aria-label="Main navigation">
          <NavLink
            to="/assistant"
            aria-label="Knowledge assistant"
            title={collapsed ? "Knowledge assistant" : undefined}
            className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
          >
            <Icon name="chat" />
            <span className="sidebar-text">Knowledge assistant</span>
          </NavLink>
          <NavLink
            to="/documents"
            aria-label="Document library"
            title={collapsed ? "Document library" : undefined}
            className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
          >
            <Icon name="folder" />
            <span className="sidebar-text">Document library</span>
          </NavLink>
        </nav>
        <div className="sidebar-bottom">
          <div className="scope-note" title={collapsed ? "Permission-aware access" : undefined}>
            <Icon name="shield" />
            <div className="sidebar-text">
              Permission-aware access
              <small>
                {user.role === "Executive"
                  ? "Across departments"
                  : `${user.department} & shared documents`}
              </small>
            </div>
          </div>
          <div className="sidebar-profile">
            <span className="avatar" title={`${user.name} · ${user.role}`}>{initials}</span>
            <div className="sidebar-text">
              <strong>{user.name}</strong>
              <small>{user.role}</small>
            </div>
            <button
              className="icon-button"
              onClick={signOut}
              aria-label="Sign out"
              title="Sign out"
            >
              <Icon name="logout" size={18} />
            </button>
          </div>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace
            <Icon name="chevron" size={14} />
            <strong>
              {pathname === "/documents"
                ? "Document library"
                : "Knowledge assistant"}
            </strong>
          </div>
        </header>
        <main className="workspace-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
