"use client";

import type { CSSProperties, ReactNode } from "react";

export interface CardProps {
  children: ReactNode;
  title?: string;
  subtitle?: string;
  headerAction?: ReactNode;
  padding?: string;
  className?: string;
  style?: CSSProperties;
}

const shell: CSSProperties = {
  background: "#ffffff",
  border: "1px solid #e5e7eb",
  borderRadius: 8,
  boxShadow: "0 1px 2px rgba(15, 23, 42, 0.08)"
};

export function Card({
  children,
  title,
  subtitle,
  headerAction,
  padding = "16px",
  className,
  style
}: CardProps) {
  const hasHeader = Boolean(title || subtitle || headerAction);
  return (
    <section className={className} style={{ ...shell, ...style }}>
      {hasHeader ? (
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            gap: 12,
            padding,
            borderBottom: title || subtitle ? "1px solid #e5e7eb" : undefined
          }}
        >
          <div style={{ minWidth: 0 }}>
            {title ? (
              <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: "#0f172a" }}>{title}</h2>
            ) : null}
            {subtitle ? (
              <p style={{ margin: title ? "6px 0 0" : 0, fontSize: 13, color: "#64748b" }}>{subtitle}</p>
            ) : null}
          </div>
          {headerAction ? <div style={{ flexShrink: 0 }}>{headerAction}</div> : null}
        </div>
      ) : null}
      <div style={{ padding: hasHeader ? padding : padding }}>{children}</div>
    </section>
  );
}
