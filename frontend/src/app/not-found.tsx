import Link from "next/link";

export default function NotFound() {
  return (
    <main
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
      <h1 style={{ fontSize: 72, fontWeight: 700, color: "var(--border)", marginBottom: 0 }}>404</h1>
      <p style={{ fontSize: 18, color: "var(--muted)", marginBottom: 24 }}>
        This page could not be found.
      </p>
      <div style={{ display: "flex", gap: 12 }}>
        <Link href="/" className="btn">
          Home
        </Link>
        <Link href="/dashboard" className="btn btn-primary">
          Dashboard
        </Link>
      </div>
    </main>
  );
}
