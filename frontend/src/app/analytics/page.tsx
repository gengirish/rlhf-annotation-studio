"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { AppShell } from "@/components/AppShell";
import { api, type SessionMetrics, type SessionTimeline } from "@/lib/api";
import { useAppStore } from "@/lib/state/store";

function formatDurationSeconds(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds || 0));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  return `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
}

function completionPercent(rate: number): number {
  if (Number.isNaN(rate)) return 0;
  if (rate > 1 && rate <= 100) return Math.round(Math.min(100, Math.max(0, rate)));
  if (rate <= 1) return Math.round(Math.min(100, Math.max(0, rate * 100)));
  return 100;
}

export default function AnalyticsPage() {
  const router = useRouter();
  const user = useAppStore((s) => s.user);
  const sessionId = useAppStore((s) => s.sessionId);

  const [metrics, setMetrics] = useState<SessionMetrics | null>(null);
  const [timeline, setTimeline] = useState<SessionTimeline | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user || !sessionId) {
      router.push("/auth");
    }
  }, [user, sessionId, router]);

  useEffect(() => {
    async function load() {
      if (!sessionId) return;
      setLoading(true);
      try {
        const [m, t] = await Promise.all([
          api.getSessionMetrics(sessionId),
          api.getSessionTimeline(sessionId)
        ]);
        setMetrics(m);
        setTimeline(t);
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Failed to load analytics");
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, [sessionId]);

  const dimensionEntries = useMemo(() => {
    if (!metrics?.dimension_averages) return [];
    return Object.entries(metrics.dimension_averages).sort(([a], [b]) => a.localeCompare(b));
  }, [metrics]);

  const dimensionMax = useMemo(() => {
    const vals = dimensionEntries.map(([, v]) => v);
    return Math.max(1, ...vals, 5);
  }, [dimensionEntries]);

  const tasksByTypeEntries = useMemo(() => {
    if (!metrics?.tasks_by_type) return [];
    return Object.entries(metrics.tasks_by_type);
  }, [metrics]);

  const timelinePoints = timeline?.points ?? [];

  const completionPct = metrics ? completionPercent(metrics.completion_rate) : 0;

  if (!user || !sessionId) {
    return null;
  }

  return (
    <AppShell>
      <header
        className="card"
        style={{
          padding: 16,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 12
        }}
      >
        <div>
          <h1 style={{ margin: 0 }}>Session analytics</h1>
          <p style={{ margin: "6px 0 0", color: "var(--muted)" }}>Metrics for your current session</p>
        </div>
      </header>

      {loading ? (
        <p style={{ marginTop: 18, color: "var(--muted)" }}>Loading analytics…</p>
      ) : !metrics ? (
        <p style={{ marginTop: 18, color: "var(--muted)" }}>No metrics available.</p>
      ) : (
        <>
          <section
            style={{
              marginTop: 18,
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
              gap: 12
            }}
          >
            <article className="card" style={{ padding: 14 }}>
              <h3 style={{ marginTop: 0 }}>Completion rate</h3>
              <p style={{ fontSize: 26, margin: 0, color: "#6366f1", fontWeight: 700 }}>{completionPct}%</p>
              <p style={{ margin: "8px 0 0", fontSize: 13, color: "var(--muted)" }}>
                {metrics.completed_tasks} done · {metrics.pending_tasks} pending · {metrics.skipped_tasks} skipped
              </p>
            </article>

            <article className="card" style={{ padding: 14 }}>
              <h3 style={{ marginTop: 0 }}>Total time</h3>
              <p style={{ fontSize: 26, margin: 0 }}>{formatDurationSeconds(metrics.total_time_seconds)}</p>
              <p style={{ margin: "8px 0 0", fontSize: 13, color: "var(--muted)" }}>
                Across {metrics.total_tasks} tasks
              </p>
            </article>

            <article className="card" style={{ padding: 14 }}>
              <h3 style={{ marginTop: 0 }}>Avg time / task</h3>
              <p style={{ fontSize: 26, margin: 0 }}>{formatDurationSeconds(metrics.avg_time_seconds)}</p>
            </article>

            <article className="card" style={{ padding: 14 }}>
              <h3 style={{ marginTop: 0 }}>Median time / task</h3>
              <p style={{ fontSize: 26, margin: 0 }}>{formatDurationSeconds(metrics.median_time_seconds)}</p>
            </article>
          </section>

          <section className="card" style={{ marginTop: 18, padding: 16 }}>
            <h2 style={{ marginTop: 0 }}>Dimension averages</h2>
            {dimensionEntries.length === 0 ? (
              <p style={{ color: "var(--muted)" }}>No dimension data yet.</p>
            ) : (
              <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
                {dimensionEntries.map(([name, value]) => {
                  const pct = Math.min(100, (value / dimensionMax) * 100);
                  return (
                    <li key={name} style={{ marginBottom: 14 }}>
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          marginBottom: 4,
                          fontSize: 14
                        }}
                      >
                        <span>{name}</span>
                        <span style={{ color: "var(--muted)" }}>{value.toFixed(2)}</span>
                      </div>
                      <div
                        style={{
                          height: 10,
                          borderRadius: 6,
                          background: "#e2e8f0",
                          overflow: "hidden"
                        }}
                      >
                        <div
                          style={{
                            width: `${pct}%`,
                            height: "100%",
                            background: "#6366f1",
                            borderRadius: 6,
                            transition: "width 0.2s ease"
                          }}
                        />
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>

          <section className="card" style={{ marginTop: 18, padding: 16 }}>
            <h2 style={{ marginTop: 0 }}>Tasks by type</h2>
            {tasksByTypeEntries.length === 0 ? (
              <p style={{ color: "var(--muted)" }}>No breakdown available.</p>
            ) : (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {tasksByTypeEntries.map(([type, count]) => (
                  <span
                    key={type}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 6,
                      padding: "6px 12px",
                      borderRadius: 999,
                      background: "#eef2ff",
                      color: "#3730a3",
                      border: "1px solid #c7d2fe",
                      fontSize: 14
                    }}
                  >
                    <span>{type}</span>
                    <strong>{count}</strong>
                  </span>
                ))}
              </div>
            )}
          </section>

          <section className="card" style={{ marginTop: 18, padding: 16, marginBottom: 24 }}>
            <h2 style={{ marginTop: 0 }}>Completion timeline</h2>
            {timelinePoints.length === 0 ? (
              <p style={{ color: "var(--muted)" }}>No revision history yet.</p>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table
                  style={{
                    width: "100%",
                    borderCollapse: "collapse",
                    fontSize: 14
                  }}
                >
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--border)", textAlign: "left" }}>
                      <th style={{ padding: "10px 8px", color: "var(--muted)", fontWeight: 600 }}>Revision</th>
                      <th style={{ padding: "10px 8px", color: "var(--muted)", fontWeight: 600 }}>Timestamp</th>
                      <th style={{ padding: "10px 8px", color: "var(--muted)", fontWeight: 600 }}>Completed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {timelinePoints.map((pt) => (
                      <tr key={`${pt.revision_number}-${pt.created_at}`} style={{ borderBottom: "1px solid var(--border)" }}>
                        <td style={{ padding: "10px 8px" }}>{pt.revision_number}</td>
                        <td style={{ padding: "10px 8px", color: "var(--muted)" }}>
                          {new Date(pt.created_at).toLocaleString()}
                        </td>
                        <td style={{ padding: "10px 8px", fontWeight: 600 }}>{pt.completed_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </AppShell>
  );
}
