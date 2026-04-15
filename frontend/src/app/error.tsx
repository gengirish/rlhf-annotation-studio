"use client";

import { useEffect } from "react";

export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error("Unhandled error:", error);
  }, [error]);

  return (
    <main
      role="alert"
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "60vh",
        padding: 40,
        textAlign: "center",
      }}
    >
      <div aria-hidden="true" style={{ fontSize: 48, marginBottom: 16 }}>⚠</div>
      <h1 style={{ fontSize: 24, fontWeight: 600, marginBottom: 8 }}>Something went wrong</h1>
      <p style={{ color: "var(--muted)", maxWidth: 420, marginBottom: 24 }}>
        An unexpected error occurred. Please try again, or contact support if the problem persists.
      </p>
      {error.digest && (
        <p style={{ fontSize: 12, color: "var(--muted)", marginBottom: 16 }}>
          Error ID: {error.digest}
        </p>
      )}
      <button
        onClick={reset}
        className="btn btn-primary"
      >
        Try again
      </button>
    </main>
  );
}
