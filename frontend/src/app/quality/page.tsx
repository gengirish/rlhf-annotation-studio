"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { QualityTimeline } from "@/components/charts/QualityTimeline";
import { Badge, Button, Card, EmptyState, Modal, StatCard, Table, type Column } from "@/components/ui";
import { qualityApi } from "@/lib/api-extensions";
import { useAppStore } from "@/lib/state/store";
import type {
  CalibrationTest,
  QualityDashboard,
  QualityDriftAlert,
  QualityLeaderboardEntry
} from "@/types/extensions";

function pct(n: number): string {
  if (n <= 1 && n >= 0) return `${Math.round(n * 100)}%`;
  return `${Math.round(n)}%`;
}

function parseDashboard(raw: unknown): QualityDashboard | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const timelineRaw = o.timeline;
  const timeline =
    Array.isArray(timelineRaw)
      ? timelineRaw
          .map((p) => {
            if (!p || typeof p !== "object") return null;
            const q = p as Record<string, unknown>;
            const date = String(q.date ?? q.day ?? "");
            const score = Number(q.score ?? q.value ?? 0);
            return date ? { date, score: score > 1 ? score / 100 : score } : null;
          })
          .filter(Boolean) as { date: string; score: number }[]
      : undefined;
  return {
    overall_trust_score: Number(o.overall_trust_score ?? o.overallTrustScore ?? 0),
    active_annotators: Number(o.active_annotators ?? o.activeAnnotators ?? 0),
    calibration_pass_rate: Number(o.calibration_pass_rate ?? o.calibrationPassRate ?? 0),
    avg_gold_accuracy: Number(o.avg_gold_accuracy ?? o.avgGoldAccuracy ?? 0),
    timeline
  };
}

function parseLeaderboard(raw: unknown): QualityLeaderboardEntry[] {
  const rows = Array.isArray(raw) ? raw : (raw as { entries?: unknown })?.entries;
  if (!Array.isArray(rows)) return [];
  return rows.map((r, idx) => {
    if (!r || typeof r !== "object") {
      return {
        rank: idx + 1,
        annotator_id: "",
        trust_score: 0,
        tasks_completed: 0,
        gold_accuracy: 0,
        status: "active"
      };
    }
    const o = r as Record<string, unknown>;
    return {
      rank: Number(o.rank ?? idx + 1),
      annotator_id: String(o.annotator_id ?? o.annotatorId ?? ""),
      name: o.name !== undefined ? String(o.name) : undefined,
      trust_score: Number(o.trust_score ?? o.trustScore ?? 0),
      tasks_completed: Number(o.tasks_completed ?? o.tasksCompleted ?? 0),
      gold_accuracy: Number(o.gold_accuracy ?? o.goldAccuracy ?? 0),
      status: String(o.status ?? "active")
    };
  });
}

function parseDriftAlerts(raw: unknown): QualityDriftAlert[] {
  const rows = Array.isArray(raw) ? raw : (raw as { alerts?: unknown })?.alerts;
  if (!Array.isArray(rows)) return [];
  return rows
    .map((r, i) => {
      if (!r || typeof r !== "object") return null;
      const o = r as Record<string, unknown>;
      return {
        id: String(o.id ?? `drift-${i}`),
        annotator_id: String(o.annotator_id ?? ""),
        annotator_name: o.annotator_name !== undefined ? String(o.annotator_name) : undefined,
        severity: (o.severity === "critical" ? "critical" : "warning") as "warning" | "critical",
        message: String(o.message ?? "Quality drift detected"),
        metric_delta: Number(o.metric_delta ?? o.delta ?? 0),
        detected_at: String(o.detected_at ?? o.detectedAt ?? new Date().toISOString())
      };
    })
    .filter(Boolean) as QualityDriftAlert[];
}

function parseCalibrationTests(raw: unknown): CalibrationTest[] {
  const rows = Array.isArray(raw) ? raw : (raw as { tests?: unknown })?.tests;
  if (!Array.isArray(rows)) return [];
  return rows
    .map((r, i) => {
      if (!r || typeof r !== "object") return null;
      const o = r as Record<string, unknown>;
      return {
        id: String(o.id ?? `cal-${i}`),
        name: String(o.name ?? "Calibration"),
        pass_rate: Number(o.pass_rate ?? o.passRate ?? 0),
        attempts: Number(o.attempts ?? 0),
        last_run_at: o.last_run_at !== undefined ? String(o.last_run_at) : undefined,
        status: String(o.status ?? "active")
      };
    })
    .filter(Boolean) as CalibrationTest[];
}

function statusBadgeVariant(
  status: string
): "default" | "success" | "warning" | "danger" | "info" {
  const s = status.toLowerCase();
  if (s === "active" || s === "approved") return "success";
  if (s === "calibrating" || s === "pending") return "warning";
  if (s === "suspended" || s === "rejected") return "danger";
  return "default";
}

export default function QualityPage() {
  const router = useRouter();
  const user = useAppStore((s) => s.user);
  const sessionId = useAppStore((s) => s.sessionId);

  const [narrow, setNarrow] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dashboard, setDashboard] = useState<QualityDashboard | null>(null);
  const [leaderboard, setLeaderboard] = useState<QualityLeaderboardEntry[]>([]);
  const [driftAlerts, setDriftAlerts] = useState<QualityDriftAlert[]>([]);
  const [calibrations, setCalibrations] = useState<CalibrationTest[]>([]);
  const [calModalOpen, setCalModalOpen] = useState(false);
  const [calName, setCalName] = useState("");
  const [calSaving, setCalSaving] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 900px)");
    setNarrow(mq.matches);
    const fn = () => setNarrow(mq.matches);
    mq.addEventListener("change", fn);
    return () => mq.removeEventListener("change", fn);
  }, []);

  useEffect(() => {
    if (!user || !sessionId) router.push("/auth");
  }, [user, sessionId, router]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [dashRaw, boardRaw, driftRaw, calRaw] = await Promise.all([
        qualityApi.getDashboard().catch(() => null),
        qualityApi.getLeaderboard().catch(() => null),
        qualityApi.listDriftAlerts().catch(() => null),
        qualityApi.getCalibrationTests().catch(() => null)
      ]);
      setDashboard(parseDashboard(dashRaw));
      setLeaderboard(parseLeaderboard(boardRaw));
      setDriftAlerts(parseDriftAlerts(driftRaw));
      setCalibrations(parseCalibrationTests(calRaw));
      if (!dashRaw && !boardRaw && !driftRaw && !calRaw) {
        setError("Quality API is unavailable or returned no data.");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load quality data");
      toast.error("Could not load quality dashboard");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (sessionId) void load();
  }, [sessionId, load]);

  const leaderboardColumns: Column<QualityLeaderboardEntry>[] = useMemo(
    () => [
      { key: "rank", header: "Rank" },
      {
        key: "name",
        header: "Name",
        render: (_, row) => row.name || row.annotator_id || "—"
      },
      {
        key: "trust_score",
        header: "Trust score",
        render: (v) => pct(Number(v))
      },
      { key: "tasks_completed", header: "Tasks" },
      {
        key: "gold_accuracy",
        header: "Gold accuracy",
        render: (v) => pct(Number(v))
      },
      {
        key: "status",
        header: "Status",
        render: (v) => <Badge variant={statusBadgeVariant(String(v))}>{String(v)}</Badge>
      }
    ],
    []
  );

  const calColumns: Column<CalibrationTest>[] = useMemo(
    () => [
      { key: "name", header: "Test" },
      {
        key: "pass_rate",
        header: "Pass rate",
        render: (v) => pct(Number(v))
      },
      { key: "attempts", header: "Attempts" },
      {
        key: "last_run_at",
        header: "Last run",
        render: (v) => (v ? new Date(String(v)).toLocaleString() : "—")
      },
      {
        key: "status",
        header: "Status",
        render: (v) => <Badge variant={statusBadgeVariant(String(v))}>{String(v)}</Badge>
      }
    ],
    []
  );

  async function handleCreateCalibration() {
    if (!calName.trim()) {
      toast.error("Name is required");
      return;
    }
    setCalSaving(true);
    try {
      await qualityApi.createCalibrationTest({ name: calName.trim() });
      toast.success("Calibration test created");
      setCalModalOpen(false);
      setCalName("");
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Create failed");
    } finally {
      setCalSaving(false);
    }
  }

  if (!user || !sessionId) return null;

  const trust = dashboard?.overall_trust_score ?? 0;
  const timelineData = dashboard?.timeline ?? [];

  return (
    <main className="container">
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
          <h1 style={{ margin: 0 }}>Annotation Quality</h1>
          <p style={{ margin: "6px 0 0", color: "var(--muted)" }}>
            Trust scores, calibration health, and drift monitoring
          </p>
        </div>
        <Link href="/dashboard" className="btn">
          ← Dashboard
        </Link>
      </header>

      {error && !loading ? (
        <p style={{ marginTop: 14, color: "#b45309", fontSize: 14 }}>{error}</p>
      ) : null}

      <section
        style={{
          marginTop: 18,
          display: "grid",
          gridTemplateColumns: narrow ? "1fr" : "repeat(4, minmax(0, 1fr))",
          gap: 12
        }}
      >
        <StatCard label="Overall trust score" value={loading ? "…" : pct(trust)} icon="◎" />
        <StatCard
          label="Active annotators"
          value={loading ? "…" : dashboard?.active_annotators ?? "—"}
          icon="◉"
        />
        <StatCard
          label="Calibration pass rate"
          value={loading ? "…" : pct(dashboard?.calibration_pass_rate ?? 0)}
          icon="✓"
        />
        <StatCard
          label="Avg gold accuracy"
          value={loading ? "…" : pct(dashboard?.avg_gold_accuracy ?? 0)}
          icon="★"
        />
      </section>

      <div style={{ marginTop: 18 }}>
        <Card title="Quality trend" subtitle="Rolling trust / accuracy from the quality API">
          {loading ? (
            <p style={{ color: "#64748b" }}>Loading…</p>
          ) : timelineData.length === 0 ? (
            <EmptyState
              title="No timeline series"
              description="When /quality/dashboard includes a timeline, scores render here as a sparkline."
            />
          ) : (
            <QualityTimeline dataPoints={timelineData} height={140} width={narrow ? 320 : 520} />
          )}
        </Card>
      </div>

      <div style={{ marginTop: 18 }}>
        <Card title="Leaderboard" subtitle="Top performers by trust and gold agreement">
          <Table
            columns={leaderboardColumns}
            data={leaderboard}
            loading={loading}
            emptyMessage="No leaderboard data yet. Connect the quality API to populate this table."
          />
        </Card>
      </div>

      <div style={{ marginTop: 18 }}>
        <Card title="Drift alerts" subtitle="Annotators with declining quality signals">
          {loading ? (
            <p style={{ color: "#64748b" }}>Loading…</p>
          ) : driftAlerts.length === 0 ? (
            <EmptyState
              title="No drift alerts"
              description="When the quality service detects regressions, they will appear here with severity and recommended actions."
            />
          ) : (
            <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
              {driftAlerts.map((a) => (
                <li
                  key={a.id}
                  style={{
                    padding: 14,
                    border: "1px solid #e5e7eb",
                    borderRadius: 8,
                    marginBottom: 10,
                    background: a.severity === "critical" ? "#fef2f2" : "#fffbeb"
                  }}
                >
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center" }}>
                    <Badge variant={a.severity === "critical" ? "danger" : "warning"}>{a.severity}</Badge>
                    <strong>{a.annotator_name || a.annotator_id}</strong>
                    <span style={{ color: "#64748b", fontSize: 13 }}>
                      Δ {a.metric_delta > 0 ? "+" : ""}
                      {a.metric_delta.toFixed(2)}
                    </span>
                  </div>
                  <p style={{ margin: "8px 0 0", fontSize: 14 }}>{a.message}</p>
                  <p style={{ margin: "6px 0 0", fontSize: 12, color: "#94a3b8" }}>
                    {new Date(a.detected_at).toLocaleString()}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <div style={{ marginTop: 18 }}>
        <Card
          title="Calibration tests"
          subtitle="Gold and rubric checks"
          headerAction={
            <Button variant="primary" size="sm" onClick={() => setCalModalOpen(true)}>
              New test
            </Button>
          }
        >
          <Table
            columns={calColumns}
            data={calibrations}
            loading={loading}
            emptyMessage="No calibration tests. Create one to track pass rates over time."
          />
        </Card>
      </div>

      <Modal
        isOpen={calModalOpen}
        onClose={() => !calSaving && setCalModalOpen(false)}
        title="Create calibration test"
        footer={
          <>
            <Button variant="secondary" onClick={() => setCalModalOpen(false)} disabled={calSaving}>
              Cancel
            </Button>
            <Button variant="primary" loading={calSaving} onClick={() => void handleCreateCalibration()}>
              Create
            </Button>
          </>
        }
      >
        <label style={{ display: "grid", gap: 6 }}>
          <span style={{ fontSize: 13, color: "#64748b" }}>Test name</span>
          <input
            className="input"
            value={calName}
            onChange={(e) => setCalName(e.target.value)}
            placeholder="e.g. Q2 rubric calibration"
          />
        </label>
      </Modal>
    </main>
  );
}
