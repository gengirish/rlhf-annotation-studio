"use client";

import type { CSSProperties, ReactNode } from "react";
import { useCallback, useEffect, useId, useRef } from "react";

export interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  size?: "sm" | "md" | "lg";
  footer?: ReactNode;
}

const sizes: Record<NonNullable<ModalProps["size"]>, number> = {
  sm: 400,
  md: 560,
  lg: 720
};

export function Modal({ isOpen, onClose, title, children, size = "md", footer }: ModalProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const titleId = useId();

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [isOpen, onClose]);

  const trapFocus = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key !== "Tab" || !panelRef.current) return;
      const q = panelRef.current.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      const list = Array.from(q).filter((el) => !el.hasAttribute("disabled"));
      if (list.length === 0) return;
      const first = list[0];
      const last = list[list.length - 1];
      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last.focus();
        }
      } else if (document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    },
    []
  );

  useEffect(() => {
    if (!isOpen || !panelRef.current) return;
    const q = panelRef.current.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    const list = Array.from(q).filter((el) => !el.hasAttribute("disabled"));
    list[0]?.focus();
  }, [isOpen]);

  if (!isOpen) return null;

  const overlay: CSSProperties = {
    position: "fixed",
    inset: 0,
    background: "rgba(15, 23, 42, 0.45)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: 16,
    zIndex: 1000
  };

  const panel: CSSProperties = {
    width: "100%",
    maxWidth: sizes[size],
    maxHeight: "min(90vh, 720px)",
    display: "flex",
    flexDirection: "column",
    background: "#fff",
    borderRadius: 12,
    border: "1px solid #e5e7eb",
    boxShadow: "0 25px 50px -12px rgba(15, 23, 42, 0.25)",
    overflow: "hidden"
  };

  return (
    <div
      role="presentation"
      style={overlay}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        style={panel}
        onKeyDown={trapFocus}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
            padding: "14px 18px",
            borderBottom: "1px solid #e5e7eb",
            flexShrink: 0
          }}
        >
          <h2 id={titleId} style={{ margin: 0, fontSize: 17, fontWeight: 600 }}>
            {title}
          </h2>
          <button
            type="button"
            aria-label="Close"
            onClick={onClose}
            style={{
              border: "none",
              background: "#f1f5f9",
              width: 36,
              height: 36,
              borderRadius: 8,
              cursor: "pointer",
              fontSize: 18,
              lineHeight: 1,
              color: "#475569"
            }}
          >
            ×
          </button>
        </div>
        <div style={{ padding: 18, overflowY: "auto", flex: 1 }}>{children}</div>
        {footer ? (
          <div
            style={{
              padding: "12px 18px",
              borderTop: "1px solid #e5e7eb",
              display: "flex",
              justifyContent: "flex-end",
              gap: 10,
              flexShrink: 0,
              background: "#f9fafb"
            }}
          >
            {footer}
          </div>
        ) : null}
      </div>
    </div>
  );
}
