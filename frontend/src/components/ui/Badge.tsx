"use client";

import type { CSSProperties, ReactNode } from "react";

export interface BadgeProps {
  children: ReactNode;
  variant?: "default" | "success" | "warning" | "danger" | "info";
}

const map: Record<NonNullable<BadgeProps["variant"]>, { bg: string; color: string; border: string }> = {
  default: { bg: "#f1f5f9", color: "#475569", border: "#e2e8f0" },
  success: { bg: "#ecfdf5", color: "#047857", border: "#10b981" },
  warning: { bg: "#fffbeb", color: "#b45309", border: "#f59e0b" },
  danger: { bg: "#fef2f2", color: "#b91c1c", border: "#ef4444" },
  info: { bg: "#eff6ff", color: "#1e40af", border: "#6366f1" }
};

export function Badge({ children, variant = "default" }: BadgeProps) {
  const c = map[variant];
  const style: CSSProperties = {
    display: "inline-block",
    padding: "4px 10px",
    borderRadius: 999,
    fontSize: 12,
    fontWeight: 600,
    textTransform: "lowercase",
    background: c.bg,
    color: c.color,
    border: `1px solid ${c.border}`
  };
  return <span style={style}>{children}</span>;
}
