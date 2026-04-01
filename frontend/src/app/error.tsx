"use client";

import { useEffect } from "react";

export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error("Unhandled error:", error);
  }, [error]);

  return (
    <main style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      minHeight: "60vh",
      padding: 40,
      fontFamily: "system-ui, -apple-system, sans-serif",
      textAlign: "center",
    }}>
      <div style={{
        fontSize: 48,
        marginBottom: 16,
      }}>⚠</div>
      <h1 style={{ fontSize: 24, fontWeight: 600, marginBottom: 8 }}>Something went wrong</h1>
      <p style={{ color: "#6b7280", maxWidth: 420, marginBottom: 24 }}>
        An unexpected error occurred. Please try again, or contact support if the problem persists.
      </p>
      {error.digest && (
        <p style={{ fontSize: 12, color: "#9ca3af", marginBottom: 16 }}>
          Error ID: {error.digest}
        </p>
      )}
      <button
        onClick={reset}
        style={{
          padding: "10px 24px",
          background: "#6366f1",
          color: "#fff",
          border: "none",
          borderRadius: 8,
          fontSize: 14,
          fontWeight: 500,
          cursor: "pointer",
        }}
      >
        Try again
      </button>
    </main>
  );
}
