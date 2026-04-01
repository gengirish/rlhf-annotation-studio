import Link from "next/link";

export default function NotFound() {
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
      <h1 style={{ fontSize: 72, fontWeight: 700, color: "#e5e7eb", marginBottom: 0 }}>404</h1>
      <p style={{ fontSize: 18, color: "#6b7280", marginBottom: 24 }}>
        This page could not be found.
      </p>
      <Link
        href="/dashboard"
        style={{
          padding: "10px 24px",
          background: "#6366f1",
          color: "#fff",
          borderRadius: 8,
          fontSize: 14,
          fontWeight: 500,
          textDecoration: "none",
        }}
      >
        Go to Dashboard
      </Link>
    </main>
  );
}
