"use client";

import type { CSSProperties, ReactNode } from "react";

import { Button } from "./Button";

export interface EmptyStateProps {
  title: string;
  description: string;
  action?: { label: string; onClick: () => void };
  icon?: ReactNode;
}

export function EmptyState({ title, description, action, icon }: EmptyStateProps) {
  const wrap: CSSProperties = {
    textAlign: "center",
    padding: "40px 24px",
    border: "1px dashed #e5e7eb",
    borderRadius: 12,
    background: "#f9fafb"
  };

  return (
    <div style={wrap}>
      {icon ? (
        <div style={{ fontSize: 40, marginBottom: 12, color: "#cbd5e1" }}>{icon}</div>
      ) : null}
      <h3 style={{ margin: 0, fontSize: 17, fontWeight: 600, color: "#0f172a" }}>{title}</h3>
      <p style={{ margin: "10px 0 0", fontSize: 14, color: "#64748b", maxWidth: 400, marginLeft: "auto", marginRight: "auto", lineHeight: 1.5 }}>
        {description}
      </p>
      {action ? (
        <div style={{ marginTop: 18 }}>
          <Button variant="primary" onClick={action.onClick}>
            {action.label}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
