"use client";

import type { CSSProperties } from "react";

export interface Tab {
  id: string;
  label: string;
  badge?: number;
}

export interface TabsProps {
  tabs: Tab[];
  activeTab: string;
  onChange: (tabId: string) => void;
}

export function Tabs({ tabs, activeTab, onChange }: TabsProps) {
  const btn = (active: boolean): CSSProperties => ({
    padding: "10px 16px",
    borderRadius: 8,
    border: active ? "1px solid #6366f1" : "1px solid #e5e7eb",
    background: active ? "#eef2ff" : "#fff",
    color: active ? "#4338ca" : "#0f172a",
    cursor: "pointer",
    fontWeight: active ? 600 : 500,
    fontSize: 14,
    fontFamily: "inherit",
    display: "inline-flex",
    alignItems: "center",
    gap: 8
  });

  return (
    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
      {tabs.map((t) => (
        <button key={t.id} type="button" style={btn(activeTab === t.id)} onClick={() => onChange(t.id)}>
          {t.label}
          {t.badge !== undefined && t.badge > 0 ? (
            <span
              style={{
                minWidth: 20,
                height: 20,
                padding: "0 6px",
                borderRadius: 999,
                background: activeTab === t.id ? "#6366f1" : "#e2e8f0",
                color: activeTab === t.id ? "#fff" : "#475569",
                fontSize: 12,
                fontWeight: 600,
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center"
              }}
            >
              {t.badge > 99 ? "99+" : t.badge}
            </span>
          ) : null}
        </button>
      ))}
    </div>
  );
}
