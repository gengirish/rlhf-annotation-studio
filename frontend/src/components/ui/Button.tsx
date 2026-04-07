"use client";

import type { ButtonHTMLAttributes, CSSProperties, ReactNode } from "react";
import { useId } from "react";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "danger" | "ghost";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
  icon?: ReactNode;
}

const base: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  gap: 8,
  fontWeight: 500,
  borderRadius: 8,
  cursor: "pointer",
  fontFamily: "inherit",
  border: "1px solid transparent",
  transition: "background 0.15s ease, border-color 0.15s ease, opacity 0.15s ease"
};

const sizes: Record<NonNullable<ButtonProps["size"]>, CSSProperties> = {
  sm: { padding: "6px 10px", fontSize: 13 },
  md: { padding: "10px 14px", fontSize: 14 },
  lg: { padding: "12px 18px", fontSize: 15 }
};

const variants: Record<NonNullable<ButtonProps["variant"]>, CSSProperties> = {
  primary: {
    background: "#6366f1",
    color: "#fff",
    borderColor: "#6366f1"
  },
  secondary: {
    background: "#ffffff",
    color: "#0f172a",
    borderColor: "#e5e7eb"
  },
  danger: {
    background: "#ef4444",
    color: "#fff",
    borderColor: "#ef4444"
  },
  ghost: {
    background: "transparent",
    color: "#475569",
    borderColor: "transparent"
  }
};

export function Button({
  variant = "secondary",
  size = "md",
  loading = false,
  icon,
  children,
  disabled,
  style,
  type = "button",
  ...rest
}: ButtonProps) {
  const spinId = useId().replace(/:/g, "");
  const v = variants[variant];
  const s = sizes[size];
  const isDisabled = disabled || loading;
  const spinName = `rlhf_spin_${spinId}`;
  const spinnerBorder =
    variant === "primary" || variant === "danger"
      ? "2px solid rgba(255,255,255,0.35)"
      : "2px solid rgba(99,102,241,0.25)";
  const spinnerTop =
    variant === "primary" || variant === "danger" ? "#fff" : "#6366f1";
  return (
    <button
      type={type}
      disabled={isDisabled}
      style={{
        ...base,
        ...s,
        ...v,
        opacity: isDisabled ? 0.65 : 1,
        cursor: isDisabled ? "not-allowed" : "pointer",
        ...style
      }}
      {...rest}
    >
      {loading ? (
        <>
          <style>{`@keyframes ${spinName} { to { transform: rotate(360deg); } }`}</style>
          <span
            aria-hidden
            style={{
              width: 14,
              height: 14,
              border: spinnerBorder,
              borderTopColor: spinnerTop,
              borderRadius: "50%",
              animation: `${spinName} 0.7s linear infinite`,
              flexShrink: 0
            }}
          />
        </>
      ) : (
        icon
      )}
      {children}
    </button>
  );
}
