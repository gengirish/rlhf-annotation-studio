"use client";

import { useEffect } from "react";

/**
 * Last-resort boundary for errors thrown in the root layout itself, which
 * `error.tsx` cannot catch. It replaces the whole document, so it must render
 * its own <html>/<body> and cannot rely on app styles or providers.
 */
export default function GlobalError({
  error,
  reset
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Root layout error:", error);
  }, [error]);

  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          fontFamily:
            "system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
        }}
      >
        <main
          role="alert"
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            minHeight: "100vh",
            padding: 40,
            textAlign: "center"
          }}
        >
          <div aria-hidden="true" style={{ fontSize: 48, marginBottom: 16 }}>
            ⚠
          </div>
          <h1 style={{ fontSize: 24, fontWeight: 600, marginBottom: 8 }}>
            Something went wrong
          </h1>
          <p style={{ color: "#666", maxWidth: 420, marginBottom: 24 }}>
            The application failed to load. Please try again, or contact support
            if the problem persists.
          </p>
          {error.digest && (
            <p style={{ fontSize: 12, color: "#666", marginBottom: 16 }}>
              Error ID: {error.digest}
            </p>
          )}
          <button
            onClick={reset}
            style={{
              padding: "10px 20px",
              fontSize: 14,
              fontWeight: 500,
              color: "#fff",
              background: "#111",
              border: "none",
              borderRadius: 6,
              cursor: "pointer"
            }}
          >
            Try again
          </button>
        </main>
      </body>
    </html>
  );
}
