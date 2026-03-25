"use client";

import { useEffect } from "react";

export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error("Unhandled error:", error);
  }, [error]);

  return (
    <main style={{ padding: 40, fontFamily: "system-ui" }}>
      <h1>Something went wrong</h1>
      <pre style={{ background: "#111", color: "#f88", padding: 16, borderRadius: 8, whiteSpace: "pre-wrap" }}>
        {error.message}
        {"\n\n"}
        {error.stack}
      </pre>
      <button
        onClick={reset}
        style={{ marginTop: 16, padding: "8px 16px", cursor: "pointer" }}
      >
        Try again
      </button>
    </main>
  );
}
