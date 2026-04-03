"use client";

import { FormEvent, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { useAppStore } from "@/lib/state/store";

type Mode = "login" | "register";

export default function AuthPage() {
  const router = useRouter();
  const setAuth = useAppStore((s) => s.setAuth);
  const [mode, setMode] = useState<Mode>("login");
  const [loading, setLoading] = useState(false);

  const title = useMemo(
    () => (mode === "login" ? "Sign in to continue" : "Create your account"),
    [mode]
  );

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    setLoading(true);
    try {
      const payload =
        mode === "register"
          ? await api.register({
              name: String(fd.get("name") || ""),
              email: String(fd.get("email") || ""),
              password: String(fd.get("password") || ""),
              phone: String(fd.get("phone") || "") || undefined,
              role: String(fd.get("role") || "annotator"),
            })
          : await api.login({
              email: String(fd.get("email") || ""),
              password: String(fd.get("password") || "")
            });

      setAuth({
        user: {
          id: payload.annotator.id,
          name: payload.annotator.name,
          email: payload.annotator.email,
          phone: payload.annotator.phone,
          role: payload.annotator.role,
          org_id: payload.annotator.org_id
        },
        token: payload.token,
        sessionId: payload.session_id
      });
      toast.success("Authenticated");
      router.push("/dashboard");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Authentication failed";
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="container" style={{ minHeight: "100vh", display: "grid", placeItems: "center" }}>
      <section className="card" style={{ width: "100%", maxWidth: 520, padding: 24 }}>
        <h1 style={{ marginTop: 0 }}>RLHF Annotation Studio</h1>
        <p style={{ marginTop: 8, color: "var(--muted)" }}>{title}</p>

        <div style={{ display: "flex", gap: 8, marginTop: 20, marginBottom: 20 }}>
          <button className={`btn ${mode === "login" ? "btn-primary" : ""}`} onClick={() => setMode("login")}>
            Login
          </button>
          <button
            className={`btn ${mode === "register" ? "btn-primary" : ""}`}
            onClick={() => setMode("register")}
          >
            Register
          </button>
        </div>

        <form onSubmit={handleSubmit} style={{ display: "grid", gap: 12 }}>
          {mode === "register" ? (
            <>
              <input className="input" name="name" placeholder="Full name" required />
              <input className="input" name="phone" placeholder="Phone (optional)" />
              <div>
                <label style={{ fontSize: 13, color: "var(--muted)", marginBottom: 4, display: "block" }}>
                  Role
                </label>
                <select
                  className="input"
                  name="role"
                  defaultValue="annotator"
                  style={{ width: "100%", padding: "8px 12px", cursor: "pointer" }}
                >
                  <option value="annotator">Annotator</option>
                </select>
              </div>
            </>
          ) : null}
          <input className="input" name="email" type="email" placeholder="Email" required />
          <input className="input" name="password" type="password" placeholder="Password" minLength={6} required />
          <button className="btn btn-primary" type="submit" disabled={loading}>
            {loading ? "Please wait..." : mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>
      </section>
    </main>
  );
}
