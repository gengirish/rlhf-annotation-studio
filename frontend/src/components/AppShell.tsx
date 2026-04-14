"use client";

import type { Route } from "next";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { type PropsWithChildren, useState } from "react";

import { useAppStore } from "@/lib/state/store";

interface NavItem {
  href: string;
  label: string;
  icon: string;
  roles?: string[];
}

const NAV_SECTIONS: { title: string; items: NavItem[] }[] = [
  {
    title: "Annotate",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: "⌂" },
      { href: "/exams", label: "Exams", icon: "▣" },
      { href: "/task/0", label: "Current Task", icon: "✎" }
    ]
  },
  {
    title: "Create",
    items: [
      { href: "/author", label: "Author Tasks", icon: "+" },
      { href: "/datasets", label: "Datasets", icon: "▤" }
    ]
  },
  {
    title: "Quality",
    items: [
      { href: "/reviews", label: "Review Queue", icon: "✓" },
      { href: "/auto-reviews", label: "Auto Reviews", icon: "⚡", roles: ["admin", "reviewer"] },
      { href: "/exams/review", label: "Exam Review", icon: "▤", roles: ["admin", "reviewer"] },
      { href: "/quality", label: "Quality Scores", icon: "◎" },
      { href: "/analytics", label: "Analytics", icon: "◔" }
    ]
  },
  {
    title: "Admin",
    items: [
      { href: "/team", label: "Team", icon: "◉", roles: ["admin", "reviewer"] },
      { href: "/audit", label: "Audit Log", icon: "☰", roles: ["admin"] },
      { href: "/webhooks", label: "Webhooks", icon: "⇄", roles: ["admin"] },
      { href: "/settings", label: "Settings", icon: "⚙" }
    ]
  }
];

export function AppShell({ children }: PropsWithChildren) {
  const router = useRouter();
  const pathname = usePathname();
  const user = useAppStore((s) => s.user);
  const logout = useAppStore((s) => s.logout);
  const completed = useAppStore((s) =>
    Object.values(s.annotations).filter((a) => a.status === "done").length
  );
  const total = useAppStore((s) => s.tasks.length);
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const role = user?.role || "annotator";

  function handleLogout() {
    logout();
    router.push("/auth");
  }

  function isActive(href: string) {
    if (href === "/dashboard") return pathname === "/dashboard";
    if (href.startsWith("/task/")) return pathname.startsWith("/task/");
    if (href === "/exams") {
      if (pathname.startsWith("/exams/review")) return false;
      return pathname === "/exams" || pathname.startsWith("/exams/");
    }
    if (href === "/exams/review") return pathname.startsWith("/exams/review");
    if (href === "/auto-reviews") return pathname.startsWith("/auto-reviews");
    return pathname === href;
  }

  const sidebar = (
    <nav className="shell-sidebar" data-collapsed={collapsed} data-mobile-open={mobileOpen}>
      <div className="shell-sidebar-header">
        {!collapsed && (
          <Link href="/dashboard" className="shell-logo">
            <span className="shell-logo-icon">◆</span>
            <span>RLHF Studio</span>
          </Link>
        )}
        <button
          className="shell-collapse-btn"
          onClick={() => {
            setCollapsed(!collapsed);
            setMobileOpen(false);
          }}
          title={collapsed ? "Expand" : "Collapse"}
        >
          {collapsed ? "▸" : "◂"}
        </button>
      </div>

      {total > 0 && !collapsed && (
        <div className="shell-progress">
          <div className="shell-progress-label">
            <span>Progress</span>
            <span>{completed}/{total}</span>
          </div>
          <div className="shell-progress-track">
            <div
              className="shell-progress-fill"
              style={{ width: `${total > 0 ? Math.round((completed / total) * 100) : 0}%` }}
            />
          </div>
        </div>
      )}

      <div className="shell-nav-groups">
        {NAV_SECTIONS.map((section) => {
          const visibleItems = section.items.filter(
            (item) => !item.roles || item.roles.includes(role)
          );
          if (visibleItems.length === 0) return null;
          return (
            <div key={section.title} className="shell-nav-group">
              {!collapsed && <div className="shell-nav-title">{section.title}</div>}
              {visibleItems.map((item) => (
                <Link
                  key={item.href}
                  href={item.href as Route}
                  className={`shell-nav-item ${isActive(item.href) ? "active" : ""}`}
                  onClick={() => setMobileOpen(false)}
                  title={collapsed ? item.label : undefined}
                >
                  <span className="shell-nav-icon" aria-hidden="true">{item.icon}</span>
                  {!collapsed && <span>{item.label}</span>}
                </Link>
              ))}
            </div>
          );
        })}
      </div>

      <div className="shell-sidebar-footer">
        {!collapsed && user && (
          <div className="shell-user-info">
            <div className="shell-avatar">{user.name?.charAt(0)?.toUpperCase() || "?"}</div>
            <div className="shell-user-details">
              <span className="shell-user-name">{user.name}</span>
              <span className="shell-user-role">{role}</span>
            </div>
          </div>
        )}
        <button className="shell-nav-item" onClick={handleLogout} title="Logout">
          <span className="shell-nav-icon" aria-hidden="true">⏻</span>
          {!collapsed && <span>Logout</span>}
        </button>
      </div>
    </nav>
  );

  return (
    <div className="shell-layout">
      {sidebar}
      {mobileOpen && (
        <div className="shell-overlay" onClick={() => setMobileOpen(false)} />
      )}
      <div className="shell-main">
        <header className="shell-topbar">
          <button className="shell-mobile-toggle" onClick={() => setMobileOpen(!mobileOpen)}>
            ☰
          </button>
          <Link href="/dashboard" className="shell-topbar-logo">
            <span className="shell-logo-icon">◆</span>
            <span>RLHF Studio</span>
          </Link>
          <div className="shell-topbar-right">
            {total > 0 && (
              <span className="shell-topbar-stat">{completed}/{total} done</span>
            )}
            {user?.role && user.role !== "annotator" && (
              <span className="shell-role-badge">{user.role}</span>
            )}
          </div>
        </header>
        <main className="shell-content">{children}</main>
      </div>
    </div>
  );
}
