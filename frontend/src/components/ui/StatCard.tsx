"use client";

import type { CSSProperties, ReactNode } from "react";

export interface StatCardProps {
  label: string;
  value: string | number;
  change?: { value: number; direction: "up" | "down" };
  icon?: ReactNode;
}

export function StatCard({ label, value, change, icon }: StatCardProps) {
  const shell: CSSProperties = {
    background: "#ffffff",
    border: "1px solid #e5e7eb",
    borderRadius: 8,
    boxShadow: "0 1px 2px rgba(15, 23, 42, 0.08)",
    padding: 16,
    display: "flex",
    gap: 12,
    alignItems: "flex-start",
    minHeight: 96
  };

  const trendColor =
    change?.direction === "up" ? "#10b981" : change?.direction === "down" ? "#ef4444" : "#64748b";

  return (
    <article style={shell}>
      {icon ? (
        <div
          style={{
            width: 40,
            height: 40,
            borderRadius: 10,
            background: "#eef2ff",
            color: "#6366f1",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
            fontSize: 18
          }}
        >
          {icon}
        </div>
      ) : null}
      <div style={{ minWidth: 0, flex: 1 }}>
        <p style={{ margin: 0, fontSize: 12, fontWeight: 600, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.04em" }}>
          {label}
        </p>
        <p style={{ margin: "8px 0 0", fontSize: 28, fontWeight: 700, color: "#0f172a", lineHeight: 1.1 }}>
          {value}
        </p>
        {change ? (
          <p style={{ margin: "6px 0 0", fontSize: 13, fontWeight: 600, color: trendColor }}>
            {change.direction === "up" ? "↑" : "↓"} {Math.abs(change.value)}%
            <span style={{ fontWeight: 400, color: "#94a3b8", marginLeft: 6 }}>vs prior</span>
          </p>
        ) : null}
      </div>
    </article>
  );
}
