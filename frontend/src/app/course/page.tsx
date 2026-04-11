"use client";

import type { Route } from "next";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { courseApi } from "@/lib/course-api";
import type { CourseModuleRead, CourseOverviewResponse, CourseProgressResponse } from "@/types/course";

const FONT =
  'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';
const INDIGO = "#6366f1";
const EMERALD = "#10b981";
const GRAY_50 = "#f9fafb";
const GRAY_200 = "#e5e7eb";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("rlhf_authToken");
}

export default function CourseOverviewPage() {
  const [narrow, setNarrow] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [overview, setOverview] = useState<CourseOverviewResponse | null>(null);
  const [progress, setProgress] = useState<CourseProgressResponse | null>(null);
  const [progressError, setProgressError] = useState<string | null>(null);

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 900px)");
    setNarrow(mq.matches);
    const fn = () => setNarrow(mq.matches);
    mq.addEventListener("change", fn);
    return () => mq.removeEventListener("change", fn);
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setProgressError(null);
    const token = getToken();
    try {
      const overviewPromise = courseApi.getOverview();
      const progressPromise = token
        ? courseApi.getProgress().catch((e) => {
            setProgressError(e instanceof Error ? e.message : "Could not load progress");
            return null;
          })
        : Promise.resolve<CourseProgressResponse | null>(null);
      const [o, p] = await Promise.all([overviewPromise, progressPromise]);
      setOverview(o);
      setProgress(p);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load course overview");
      setOverview(null);
      setProgress(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const onStorage = (ev: StorageEvent) => {
      if (ev.key === "rlhf_authToken") void load();
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [load]);

  const authenticated = Boolean(getToken());
  const totalSessions = overview?.total_sessions ?? 25;
  const subtitle =
    overview != null
      ? `${overview.total_modules} Modules · ${overview.total_sessions} Sessions`
      : "9 Modules · 25 Sessions";

  const completed = progress?.completed_sessions ?? 0;
  const progressPct = totalSessions > 0 ? Math.round((completed / totalSessions) * 100) : 0;
  const continueHref =
    progress?.current_session != null ? `/course/${progress.current_session}` : null;

  return (
    <AppShell>
      <style>{`
        @keyframes courseHeroShimmer {
          0% { background-position: 0% 50%; }
          100% { background-position: 100% 50%; }
        }
        @keyframes courseSpin {
          to { transform: rotate(360deg); }
        }
      `}</style>

      <div style={{ fontFamily: FONT, maxWidth: 1120, margin: "0 auto" }}>
        {/* Hero */}
        <section
          style={{
            position: "relative",
            overflow: "hidden",
            borderRadius: 16,
            padding: narrow ? "28px 20px" : "40px 44px",
            marginBottom: 28,
            background: `linear-gradient(135deg, #eef2ff 0%, ${GRAY_50} 45%, #ecfdf5 100%)`,
            border: `1px solid ${GRAY_200}`,
            boxShadow: "0 4px 24px rgba(99, 102, 241, 0.12)"
          }}
        >
          <div
            aria-hidden
            style={{
              position: "absolute",
              inset: 0,
              opacity: 0.5,
              background:
                "linear-gradient(110deg, transparent 0%, rgba(99,102,241,0.08) 40%, transparent 80%)",
              backgroundSize: "200% 200%",
              animation: "courseHeroShimmer 8s ease-in-out infinite alternate"
            }}
          />
          <div style={{ position: "relative", zIndex: 1 }}>
            <p
              style={{
                margin: 0,
                fontSize: 13,
                fontWeight: 600,
                letterSpacing: "0.06em",
                textTransform: "uppercase",
                color: "#4f46e5"
              }}
            >
              Curriculum
            </p>
            <h1
              style={{
                margin: "10px 0 0",
                fontSize: narrow ? 28 : 36,
                fontWeight: 700,
                color: "#0f172a",
                lineHeight: 1.15,
                letterSpacing: "-0.02em"
              }}
            >
              AI Code Reviewer Training
            </h1>
            <p style={{ margin: "12px 0 0", fontSize: 17, color: "#475569", maxWidth: 560 }}>
              {subtitle}
            </p>

            {loading ? (
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 24 }}>
                <div
                  style={{
                    width: 22,
                    height: 22,
                    border: `3px solid ${GRAY_200}`,
                    borderTopColor: INDIGO,
                    borderRadius: "50%",
                    animation: "courseSpin 0.75s linear infinite"
                  }}
                />
                <span style={{ color: "#64748b", fontSize: 15 }}>Loading curriculum…</span>
              </div>
            ) : null}

            {error ? (
              <div
                style={{
                  marginTop: 22,
                  padding: "14px 16px",
                  borderRadius: 8,
                  background: "#fef2f2",
                  border: "1px solid #fecaca",
                  color: "#991b1b",
                  fontSize: 14
                }}
              >
                {error}
              </div>
            ) : null}

            {!loading && !error && authenticated && progress ? (
              <div style={{ marginTop: 26 }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "baseline",
                    flexWrap: "wrap",
                    gap: 8,
                    marginBottom: 8
                  }}
                >
                  <span style={{ fontSize: 14, fontWeight: 600, color: "#334155" }}>Your progress</span>
                  <span style={{ fontSize: 14, color: "#64748b" }}>
                    <strong style={{ color: EMERALD }}>{completed}</strong> / {totalSessions} sessions
                  </span>
                </div>
                <div
                  style={{
                    height: 10,
                    borderRadius: 999,
                    background: GRAY_200,
                    overflow: "hidden",
                    boxShadow: "inset 0 1px 2px rgba(15,23,42,0.06)"
                  }}
                >
                  <div
                    style={{
                      height: "100%",
                      width: `${progressPct}%`,
                      borderRadius: 999,
                      background: `linear-gradient(90deg, ${INDIGO}, #818cf8)`,
                      transition: "width 0.4s ease"
                    }}
                  />
                </div>
                {progressError ? (
                  <p style={{ margin: "10px 0 0", fontSize: 13, color: "#b45309" }}>{progressError}</p>
                ) : null}
              </div>
            ) : null}

            {!loading && !error && authenticated && !progress && progressError ? (
              <p style={{ marginTop: 16, fontSize: 13, color: "#b45309" }}>{progressError}</p>
            ) : null}

            {!loading && !error ? (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginTop: 26 }}>
                {continueHref ? (
                  <Link
                    href={continueHref as Route}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      justifyContent: "center",
                      padding: "12px 22px",
                      borderRadius: 10,
                      background: INDIGO,
                      color: "#fff",
                      fontWeight: 600,
                      fontSize: 15,
                      textDecoration: "none",
                      boxShadow: "0 4px 14px rgba(99, 102, 241, 0.45)"
                    }}
                  >
                    Continue course
                  </Link>
                ) : authenticated ? (
                  <span style={{ fontSize: 14, color: "#64748b", alignSelf: "center" }}>
                    Pick a session below to begin or resume.
                  </span>
                ) : null}
                <Link
                  href="/auth"
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    padding: "12px 20px",
                    borderRadius: 10,
                    border: `1px solid ${GRAY_200}`,
                    background: "#fff",
                    color: "#334155",
                    fontWeight: 600,
                    fontSize: 15,
                    textDecoration: "none"
                  }}
                >
                  {authenticated ? "Account" : "Sign in for progress"}
                </Link>
              </div>
            ) : null}
          </div>
        </section>

        {/* Module grid */}
        {!loading && !error && overview ? (
          <section>
            <h2 style={{ margin: "0 0 6px", fontSize: 20, fontWeight: 700, color: "#0f172a" }}>Modules</h2>
            <p style={{ margin: "0 0 22px", color: "#64748b", fontSize: 14 }}>
              Structured path from fundamentals to production-grade review practice.
            </p>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: narrow ? "1fr" : "repeat(2, minmax(0, 1fr))",
                gap: 20
              }}
            >
              {overview.modules.map((m) => (
                <ModuleCard key={m.id} module={m} />
              ))}
            </div>
          </section>
        ) : null}

        {!loading && !error && overview && overview.modules.length === 0 ? (
          <p style={{ color: "#64748b" }}>No modules published yet.</p>
        ) : null}
      </div>
    </AppShell>
  );
}

function ModuleCard({ module: m }: { module: CourseModuleRead }) {
  return (
    <article
      style={{
        background: "#fff",
        border: `1px solid ${GRAY_200}`,
        borderRadius: 8,
        boxShadow: "0 1px 2px rgba(15, 23, 42, 0.08)",
        padding: 20,
        display: "flex",
        flexDirection: "column",
        gap: 14,
        transition: "box-shadow 0.2s ease, transform 0.2s ease"
      }}
    >
      <div style={{ display: "flex", gap: 14, alignItems: "flex-start" }}>
        <div
          style={{
            width: 44,
            height: 44,
            borderRadius: "50%",
            background: INDIGO,
            color: "#fff",
            fontWeight: 700,
            fontSize: 18,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
            boxShadow: "0 2px 8px rgba(99, 102, 241, 0.35)"
          }}
          aria-hidden
        >
          {m.number}
        </div>
        <div style={{ minWidth: 0 }}>
          <h3 style={{ margin: 0, fontSize: 17, fontWeight: 700, color: "#0f172a", lineHeight: 1.3 }}>
            {m.title}
          </h3>
          <div style={{ marginTop: 8, display: "flex", flexWrap: "wrap", gap: "8px 14px", fontSize: 13, color: "#64748b" }}>
            <span>{m.estimated_time}</span>
            <span aria-hidden style={{ color: GRAY_200 }}>
              |
            </span>
            <span>
              {m.session_count} session{m.session_count === 1 ? "" : "s"}
            </span>
          </div>
        </div>
      </div>

      {m.prerequisites ? (
        <p style={{ margin: 0, fontSize: 13, color: "#92400e", background: "#fffbeb", padding: "8px 10px", borderRadius: 6 }}>
          <strong>Prerequisites:</strong> {m.prerequisites}
        </p>
      ) : null}

      {m.skills_json?.length ? (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {m.skills_json.map((skill) => (
            <span
              key={skill}
              style={{
                fontSize: 12,
                fontWeight: 500,
                padding: "4px 10px",
                borderRadius: 999,
                background: "#eef2ff",
                color: "#4338ca",
                border: "1px solid #c7d2fe"
              }}
            >
              {skill}
            </span>
          ))}
        </div>
      ) : null}

      <div>
        <p style={{ margin: "0 0 8px", fontSize: 12, fontWeight: 600, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.04em" }}>
          Sessions
        </p>
        <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 6 }}>
          {m.sessions.map((s) => (
            <li key={s.id}>
              <Link
                href={`/course/${s.number}` as Route}
                style={{
                  display: "block",
                  fontSize: 14,
                  color: INDIGO,
                  textDecoration: "none",
                  padding: "6px 0",
                  borderBottom: "1px solid #f1f5f9"
                }}
              >
                <span style={{ color: "#94a3b8", marginRight: 8 }}>{s.number}.</span>
                {s.title}
                <span style={{ marginLeft: 8, fontSize: 12, color: "#94a3b8" }}>{s.duration}</span>
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </article>
  );
}
