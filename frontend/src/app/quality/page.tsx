"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { AppShell } from "@/components/AppShell";
import { QualityTimeline } from "@/components/charts/QualityTimeline";
import { Badge, Button, Card, EmptyState, Modal, StatCard, Table, type Column } from "@/components/ui";
import { api, type TaskPackSummary } from "@/lib/api";
import { judgeApi, qualityApi } from "@/lib/api-extensions";
import { useAppStore, useHasHydrated } from "@/lib/state/store";
import type {
  CalibrationTest,
  LLMEvaluation,
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

function formatPreference(preference: unknown): string {
  if (preference === 0) return "A";
  if (preference === 1) return "B";
  return "—";
}

function formatConfidence(confidence: unknown): string {
  if (typeof confidence !== "number" || Number.isNaN(confidence)) return "—";
  return `${Math.round(confidence * 100)}%`;
}

export default function QualityPage() {
  const router = useRouter();
  const user = useAppStore((s) => s.user);
  const sessionId = useAppStore((s) => s.sessionId);
  const hydrated = useHasHydrated();

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
  const [taskPacks, setTaskPacks] = useState<TaskPackSummary[]>([]);
  const [selectedPackId, setSelectedPackId] = useState("");
  const [judgeTaskIds, setJudgeTaskIds] = useState("");
  const [judgeModel, setJudgeModel] = useState("");
  const [judgeTemperature, setJudgeTemperature] = useState("0.1");
  const [judgeRunning, setJudgeRunning] = useState(false);
  const [judgeActingId, setJudgeActingId] = useState<string | null>(null);
  const [evaluations, setEvaluations] = useState<LLMEvaluation[]>([]);
  const [evaluationsLoading, setEvaluationsLoading] = useState(false);
  const [overrideModalOpen, setOverrideModalOpen] = useState(false);
  const [selectedEvaluation, setSelectedEvaluation] = useState<LLMEvaluation | null>(null);
  const [overridePreference, setOverridePreference] = useState("");
  const [overrideReasoning, setOverrideReasoning] = useState("");
  const [overrideDimensions, setOverrideDimensions] = useState("");
  const [overrideSaving, setOverrideSaving] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 900px)");
    setNarrow(mq.matches);
    const fn = () => setNarrow(mq.matches);
    mq.addEventListener("change", fn);
    return () => mq.removeEventListener("change", fn);
  }, []);

  useEffect(() => {
    if (hydrated && (!user || !sessionId)) router.push("/auth");
  }, [hydrated, user, sessionId, router]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const uid = useAppStore.getState().user?.id;
      const [dashRaw, boardRaw, driftRaw, calRaw] = await Promise.all([
        qualityApi.getDashboard().catch(() => null),
        qualityApi.getLeaderboard().catch(() => null),
        qualityApi.listDriftAlerts(uid).catch(() => null),
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

  useEffect(() => {
    if (!sessionId) return;
    void api
      .getAllTaskPacks()
      .then((packs) => {
        setTaskPacks(packs);
        if (packs.length > 0) {
          setSelectedPackId((prev) => prev || packs[0].id);
        }
      })
      .catch((e) => {
        toast.error(e instanceof Error ? e.message : "Failed to load task packs");
      });
  }, [sessionId]);

  const loadEvaluations = useCallback(
    async (packId: string) => {
      if (!packId) return;
      setEvaluationsLoading(true);
      try {
        const rows = await judgeApi.listEvaluations(packId);
        setEvaluations(Array.isArray(rows) ? rows : []);
      } catch (e) {
        toast.error(e instanceof Error ? e.message : "Failed to load LLM evaluations");
        setEvaluations([]);
      } finally {
        setEvaluationsLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    if (!selectedPackId) return;
    void loadEvaluations(selectedPackId);
  }, [selectedPackId, loadEvaluations]);

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

  async function handleRunJudge() {
    if (!selectedPackId) {
      toast.error("Choose a task pack first");
      return;
    }
    const t = Number(judgeTemperature);
    if (Number.isNaN(t) || t < 0 || t > 2) {
      toast.error("Temperature must be between 0 and 2");
      return;
    }
    const taskIds = judgeTaskIds
      .split(/[\s,]+/)
      .map((x) => x.trim())
      .filter(Boolean);
    setJudgeRunning(true);
    try {
      const res = await judgeApi.evaluate({
        task_pack_id: selectedPackId,
        task_ids: taskIds.length ? taskIds : undefined,
        config: {
          model: judgeModel.trim() || undefined,
          temperature: t
        }
      });
      toast.success(
        `Evaluated ${res.results.length} task${res.results.length === 1 ? "" : "s"} using ${res.judge_model}`
      );
      await loadEvaluations(selectedPackId);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Judge evaluation failed");
    } finally {
      setJudgeRunning(false);
    }
  }

  function openOverrideModal(row: LLMEvaluation) {
    setSelectedEvaluation(row);
    const human = row.human_override;
    const auto = row.evaluation_json;
    const pref =
      typeof human?.preference === "number"
        ? String(human.preference)
        : typeof auto?.preference === "number"
          ? String(auto.preference)
          : "";
    const reason =
      typeof human?.reasoning === "string"
        ? human.reasoning
        : typeof auto?.reasoning === "string"
          ? auto.reasoning
          : "";
    const dims = human?.dimensions ?? auto?.dimensions ?? {};
    setOverridePreference(pref);
    setOverrideReasoning(reason);
    setOverrideDimensions(JSON.stringify(dims, null, 2));
    setOverrideModalOpen(true);
  }

  async function handleSaveOverride() {
    if (!selectedEvaluation) return;
    const payload: {
      preference?: number;
      dimensions?: Record<string, number>;
      reasoning?: string;
    } = {};
    if (overridePreference === "0" || overridePreference === "1") {
      payload.preference = Number(overridePreference);
    }
    if (overrideReasoning.trim()) {
      payload.reasoning = overrideReasoning.trim();
    }
    if (overrideDimensions.trim()) {
      let parsed: unknown;
      try {
        parsed = JSON.parse(overrideDimensions);
      } catch {
        toast.error("Dimensions must be valid JSON");
        return;
      }
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        toast.error("Dimensions must be an object like {\"helpfulness\": 4}");
        return;
      }
      const dims: Record<string, number> = {};
      for (const [k, v] of Object.entries(parsed as Record<string, unknown>)) {
        if (typeof v !== "number" || Number.isNaN(v)) {
          toast.error(`Dimension '${k}' must be numeric`);
          return;
        }
        dims[k] = Math.round(v);
      }
      payload.dimensions = dims;
    }
    if (!payload.reasoning && payload.preference === undefined && !payload.dimensions) {
      toast.error("Set at least one override field");
      return;
    }
    setOverrideSaving(true);
    try {
      await judgeApi.overrideEvaluation(selectedEvaluation.id, payload);
      toast.success("Human override saved");
      setOverrideModalOpen(false);
      await loadEvaluations(selectedPackId);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to save override");
    } finally {
      setOverrideSaving(false);
    }
  }

  async function handleJudgeDecision(evaluationId: string, action: "accept" | "reject") {
    setJudgeActingId(evaluationId);
    try {
      if (action === "accept") {
        await judgeApi.acceptEvaluation(evaluationId);
      } else {
        await judgeApi.rejectEvaluation(evaluationId);
      }
      toast.success(action === "accept" ? "Evaluation accepted" : "Evaluation rejected");
      await loadEvaluations(selectedPackId);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to update evaluation status");
    } finally {
      setJudgeActingId(null);
    }
  }

  if (!user || !sessionId) return null;

  const trust = dashboard?.overall_trust_score ?? 0;
  const timelineData = dashboard?.timeline ?? [];
  const canRunJudge = user.role === "admin" || user.role === "reviewer";

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
          <h1 style={{ margin: 0 }}>Annotation Quality</h1>
          <p style={{ margin: "6px 0 0", color: "var(--muted)" }}>
            Trust scores, calibration health, and drift monitoring
          </p>
        </div>
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

      <div style={{ marginTop: 18 }}>
        <Card title="LLM-as-Judge" subtitle="Run automated evaluations and manage human adjudication">
          <div
            style={{
              display: "grid",
              gridTemplateColumns: narrow ? "1fr" : "2fr 1fr 1fr",
              gap: 12,
              marginBottom: 12
            }}
          >
            <label style={{ display: "grid", gap: 6 }}>
              <span style={{ fontSize: 13, color: "#64748b" }}>Task pack</span>
              <select
                className="input"
                value={selectedPackId}
                onChange={(e) => setSelectedPackId(e.target.value)}
              >
                <option value="">Select a task pack</option>
                {taskPacks.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.task_count})
                  </option>
                ))}
              </select>
            </label>

            <label style={{ display: "grid", gap: 6 }}>
              <span style={{ fontSize: 13, color: "#64748b" }}>Model (optional override)</span>
              <input
                className="input"
                placeholder="Uses backend default model"
                value={judgeModel}
                onChange={(e) => setJudgeModel(e.target.value)}
              />
            </label>

            <label style={{ display: "grid", gap: 6 }}>
              <span style={{ fontSize: 13, color: "#64748b" }}>Temperature</span>
              <input
                className="input"
                type="number"
                min={0}
                max={2}
                step={0.1}
                value={judgeTemperature}
                onChange={(e) => setJudgeTemperature(e.target.value)}
              />
            </label>
          </div>

          <label style={{ display: "grid", gap: 6, marginBottom: 12 }}>
            <span style={{ fontSize: 13, color: "#64748b" }}>
              Task IDs (optional, comma or newline separated)
            </span>
            <textarea
              className="input"
              rows={2}
              value={judgeTaskIds}
              onChange={(e) => setJudgeTaskIds(e.target.value)}
              placeholder="Leave empty to evaluate all tasks in the selected pack"
            />
          </label>

          {!canRunJudge ? (
            <p style={{ margin: "0 0 12px", color: "#92400e", fontSize: 13 }}>
              Reviewer or admin role is required to run judge evaluations.
            </p>
          ) : null}

          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 14 }}>
            <Button
              variant="primary"
              loading={judgeRunning}
              disabled={!selectedPackId || !canRunJudge}
              onClick={() => void handleRunJudge()}
            >
              Run evaluation
            </Button>
            <Button
              variant="secondary"
              loading={evaluationsLoading}
              disabled={!selectedPackId}
              onClick={() => void loadEvaluations(selectedPackId)}
            >
              Refresh results
            </Button>
          </div>

          {evaluationsLoading ? (
            <p style={{ color: "#64748b" }}>Loading evaluations…</p>
          ) : evaluations.length === 0 ? (
            <EmptyState
              title="No evaluations yet"
              description="Run an evaluation for the selected pack to populate judge results."
            />
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: "left", padding: "10px 8px", borderBottom: "1px solid #e5e7eb" }}>Task</th>
                    <th style={{ textAlign: "left", padding: "10px 8px", borderBottom: "1px solid #e5e7eb" }}>Model</th>
                    <th style={{ textAlign: "left", padding: "10px 8px", borderBottom: "1px solid #e5e7eb" }}>Preference</th>
                    <th style={{ textAlign: "left", padding: "10px 8px", borderBottom: "1px solid #e5e7eb" }}>Confidence</th>
                    <th style={{ textAlign: "left", padding: "10px 8px", borderBottom: "1px solid #e5e7eb" }}>Status</th>
                    <th style={{ textAlign: "left", padding: "10px 8px", borderBottom: "1px solid #e5e7eb" }}>Updated</th>
                    <th style={{ textAlign: "left", padding: "10px 8px", borderBottom: "1px solid #e5e7eb" }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {evaluations.map((row) => {
                    const prefSource = row.human_override?.preference ?? row.evaluation_json?.preference;
                    return (
                      <tr key={row.id} style={{ background: "#fff" }}>
                        <td style={{ padding: "10px 8px", borderBottom: "1px solid #e5e7eb" }}>{row.task_id}</td>
                        <td style={{ padding: "10px 8px", borderBottom: "1px solid #e5e7eb" }}>{row.judge_model}</td>
                        <td style={{ padding: "10px 8px", borderBottom: "1px solid #e5e7eb" }}>{formatPreference(prefSource)}</td>
                        <td style={{ padding: "10px 8px", borderBottom: "1px solid #e5e7eb" }}>{formatConfidence(row.confidence)}</td>
                        <td style={{ padding: "10px 8px", borderBottom: "1px solid #e5e7eb" }}>
                          <Badge variant={statusBadgeVariant(row.status)}>{row.status}</Badge>
                        </td>
                        <td style={{ padding: "10px 8px", borderBottom: "1px solid #e5e7eb", whiteSpace: "nowrap" }}>
                          {new Date(row.updated_at).toLocaleString()}
                        </td>
                        <td style={{ padding: "10px 8px", borderBottom: "1px solid #e5e7eb" }}>
                          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                            <Button
                              size="sm"
                              variant="secondary"
                              onClick={() => openOverrideModal(row)}
                            >
                              Override
                            </Button>
                            <Button
                              size="sm"
                              variant="primary"
                              disabled={judgeActingId === row.id}
                              onClick={() => void handleJudgeDecision(row.id, "accept")}
                            >
                              Accept
                            </Button>
                            <Button
                              size="sm"
                              variant="danger"
                              disabled={judgeActingId === row.id}
                              onClick={() => void handleJudgeDecision(row.id, "reject")}
                            >
                              Reject
                            </Button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
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

      <Modal
        isOpen={overrideModalOpen}
        onClose={() => !overrideSaving && setOverrideModalOpen(false)}
        title="Apply human override"
        footer={
          <>
            <Button variant="secondary" disabled={overrideSaving} onClick={() => setOverrideModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" loading={overrideSaving} onClick={() => void handleSaveOverride()}>
              Save override
            </Button>
          </>
        }
      >
        <div style={{ display: "grid", gap: 12 }}>
          <p style={{ margin: 0, color: "#64748b", fontSize: 13 }}>
            Task: <strong>{selectedEvaluation?.task_id ?? "—"}</strong>
          </p>
          <label style={{ display: "grid", gap: 6 }}>
            <span style={{ fontSize: 13, color: "#64748b" }}>Preference</span>
            <select
              className="input"
              value={overridePreference}
              onChange={(e) => setOverridePreference(e.target.value)}
            >
              <option value="">No override</option>
              <option value="0">A is better</option>
              <option value="1">B is better</option>
            </select>
          </label>
          <label style={{ display: "grid", gap: 6 }}>
            <span style={{ fontSize: 13, color: "#64748b" }}>Reasoning</span>
            <textarea
              className="input"
              rows={4}
              value={overrideReasoning}
              onChange={(e) => setOverrideReasoning(e.target.value)}
              placeholder="Optional human adjudication reasoning"
            />
          </label>
          <label style={{ display: "grid", gap: 6 }}>
            <span style={{ fontSize: 13, color: "#64748b" }}>Dimensions JSON</span>
            <textarea
              className="input"
              rows={6}
              value={overrideDimensions}
              onChange={(e) => setOverrideDimensions(e.target.value)}
              placeholder='{"helpfulness": 5, "safety": 4}'
              style={{ fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" }}
            />
          </label>
        </div>
      </Modal>
    </AppShell>
  );
}
