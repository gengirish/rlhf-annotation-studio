"use client";

import type { CSSProperties } from "react";

export interface PaginationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

const btn: CSSProperties = {
  minWidth: 36,
  height: 36,
  padding: "0 10px",
  borderRadius: 8,
  border: "1px solid #e5e7eb",
  background: "#fff",
  cursor: "pointer",
  fontSize: 14,
  fontFamily: "inherit",
  color: "#0f172a"
};

export function Pagination({ currentPage, totalPages, onPageChange }: PaginationProps) {
  if (totalPages <= 1) return null;

  const pages: number[] = [];
  const radius = 2;
  for (let p = 1; p <= totalPages; p++) {
    if (p === 1 || p === totalPages || (p >= currentPage - radius && p <= currentPage + radius)) {
      pages.push(p);
    } else if (pages[pages.length - 1] !== -1) {
      pages.push(-1);
    }
  }

  return (
    <nav
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        flexWrap: "wrap",
        marginTop: 12
      }}
      aria-label="Pagination"
    >
      <button
        type="button"
        style={{ ...btn, opacity: currentPage <= 1 ? 0.45 : 1 }}
        disabled={currentPage <= 1}
        onClick={() => onPageChange(currentPage - 1)}
      >
        Prev
      </button>
      {pages.map((p, i) =>
        p === -1 ? (
          <span key={`e-${i}`} style={{ padding: "0 4px", color: "#94a3b8" }}>
            …
          </span>
        ) : (
          <button
            key={p}
            type="button"
            style={{
              ...btn,
              borderColor: p === currentPage ? "#6366f1" : "#e5e7eb",
              background: p === currentPage ? "#eef2ff" : "#fff",
              color: p === currentPage ? "#4338ca" : "#0f172a",
              fontWeight: p === currentPage ? 600 : 400
            }}
            onClick={() => onPageChange(p)}
          >
            {p}
          </button>
        )
      )}
      <button
        type="button"
        style={{ ...btn, opacity: currentPage >= totalPages ? 0.45 : 1 }}
        disabled={currentPage >= totalPages}
        onClick={() => onPageChange(currentPage + 1)}
      >
        Next
      </button>
      <span style={{ fontSize: 13, color: "#64748b", marginLeft: 8 }}>
        Page {currentPage} of {totalPages}
      </span>
    </nav>
  );
}
