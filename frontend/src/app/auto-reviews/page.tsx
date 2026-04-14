"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Modal } from "@/components/ui/Modal";
import { Pagination } from "@/components/ui/Pagination";
import { StatCard } from "@/components/ui/StatCard";
import api from "@/lib/api";
import { judgeApi } from "@/lib/api-extensions";
import { useAppStore } from "@/lib/state/store";
import type { LLMEvaluation, HumanOverrideRequest } from "@/types/extensions";

interface TaskPackOption {
  id: string;
  name: string;
}

const PAGE_SIZE = 20;

function statusVariant(s: string): "default" | "success" | "warning" | "danger" | "info" {
  switch (s) {
    case "accepted":
      return "success";
    case "rejected":
      return "danger";
    case "overridden":
      return "warning";
    case "pending":
    default:
      return "default";
  }
}

function prefLabel(pref: unknown): string {
  if (pref === 1) return "Response A";
  if (pref === 2) return "Response B";
  if (pref === 0) return "Tie";
  return "—";
}

function confidenceBar(c: number | null) {
  if (c == null) return "—";
  const pct = Math.round(c * 100);
  const color = pct >= 80 ? "#10b981" : pct >= 50 ? "#f59e0b" : "#ef4444";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 100 }}>
      <div style={{ flex: 1, height: 6, borderRadius: 3, background: "#e5e7eb" }}>
        <div style={{ width: `${pct}%`, height: "100%", borderRadius: 3, background: color }} />
      </div>
      <span style={{ fontSize: 12, fontWeight: 600, color }}>{pct}%</span>
    </div>
  );
}

export default function AutoReviewsPage() {
  const user = useAppStore((s) => s.user);
  const role = user?.role ?? "annotator";
  const canManage = role === "admin" || role === "reviewer";

  const [evals, setEvals] = useState<LLMEvaluation[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);

  const [packFilter, setPackFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [packs, setPacks] = useState<TaskPackOption[]>([]);

  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [actingId, setActingId] = useState<string | null>(null);

  const [overrideTarget, setOverrideTarget] = useState<LLMEvaluation | null>(null);
  const [overrideForm, setOverrideForm] = useState<HumanOverrideRequest>({});

  useEffect(() => {
    api.getAllTaskPacks().then((list) => {
      setPacks(list.map((p: { id: string; name: string }) => ({ id: p.id, name: p.name })));
    }).catch(() => {});
  }, []);

  const fetchPage = useCallback(
    async (p: number) => {
      setLoading(true);
      try {
        const res = await judgeApi.listAllEvaluations({
          task_pack_id: packFilter || undefined,
          status: statusFilter || undefined,
          limit: PAGE_SIZE,
          offset: (p - 1) * PAGE_SIZE,
        });
        setEvals(res.items);
        setTotal(res.total);
      } catch {
        setEvals([]);
        setTotal(0);
      } finally {
        setLoading(false);
      }
    },
    [packFilter, statusFilter]
  );

  useEffect(() => {
    setPage(1);
    void fetchPage(1);
  }, [fetchPage]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  function handlePageChange(p: number) {
    setPage(p);
    void fetchPage(p);
  }

  const stats = useMemo(() => {
    const accepted = evals.filter((e) => e.status === "accepted").length;
    const rejected = evals.filter((e) => e.status === "rejected").length;
    const pending = evals.filter((e) => e.status === "pending").length;
    const overridden = evals.filter((e) => e.status === "overridden").length;
    const withConf = evals.filter((e) => e.confidence != null);
    const avgConf =
      withConf.length > 0
        ? Math.round((withConf.reduce((s, e) => s + (e.confidence ?? 0), 0) / withConf.length) * 100)
        : 0;
    return { accepted, rejected, pending, overridden, avgConf };
  }, [evals]);

  async function handleDecision(id: string, action: "accept" | "reject") {
    setActingId(id);
    try {
      const updated =
        action === "accept"
          ? await judgeApi.acceptEvaluation(id)
          : await judgeApi.rejectEvaluation(id);
      setEvals((prev) => prev.map((e) => (e.id === id ? updated : e)));
    } catch {
      /* ignore */
    } finally {
      setActingId(null);
    }
  }

  function openOverride(ev: LLMEvaluation) {
    setOverrideTarget(ev);
    const existing = ev.human_override ?? ev.evaluation_json;
    setOverrideForm({
      preference: (existing?.preference as number) ?? null,
      reasoning: (existing?.reasoning as string) ?? "",
      dimensions: (existing?.dimensions as Record<string, number>) ?? null,
    });
  }

  async function submitOverride() {
    if (!overrideTarget) return;
    setActingId(overrideTarget.id);
    try {
      const updated = await judgeApi.overrideEvaluation(overrideTarget.id, overrideForm);
      setEvals((prev) => prev.map((e) => (e.id === overrideTarget.id ? updated : e)));
      setOverrideTarget(null);
    } catch {
      /* ignore */
    } finally {
      setActingId(null);
    }
  }

  function getPackName(id: string) {
    return packs.find((p) => p.id === id)?.name ?? id.slice(0, 8);
  }

  if (!canManage) {
    return (
      <div style={{ padding: 32, textAlign: "center", color: "#64748b" }}>
        <h2>Access Restricted</h2>
        <p>Reviewer or admin role is required to view auto-review results.</p>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", padding: "24px 16px" }}>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700, color: "#0f172a" }}>
          Auto Reviews
        </h1>
        <p style={{ margin: "6px 0 0", fontSize: 14, color: "#64748b" }}>
          LLM-as-Judge evaluation results with reasoning, dimension scores, and human adjudication
        </p>
      </div>

      {/* Stats row */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
          gap: 12,
          marginBottom: 20,
        }}
      >
        <StatCard label="Total (page)" value={total} icon="◈" />
        <StatCard label="Accepted" value={stats.accepted} icon="✓" />
        <StatCard label="Rejected" value={stats.rejected} icon="✕" />
        <StatCard label="Pending" value={stats.pending} icon="◷" />
        <StatCard label="Overridden" value={stats.overridden} icon="✎" />
        <StatCard label="Avg Confidence" value={`${stats.avgConf}%`} icon="◎" />
      </div>

      {/* Filters */}
      <Card style={{ marginBottom: 20 }}>
        <div
          style={{
            display: "flex",
            gap: 12,
            flexWrap: "wrap",
            alignItems: "flex-end",
            padding: 16,
          }}
        >
          <label style={{ display: "grid", gap: 4, flex: 1, minWidth: 200 }}>
            <span style={{ fontSize: 13, color: "#64748b", fontWeight: 500 }}>Task Pack</span>
            <select
              className="input"
              value={packFilter}
              onChange={(e) => setPackFilter(e.target.value)}
            >
              <option value="">All packs</option>
              {packs.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>

          <label style={{ display: "grid", gap: 4, minWidth: 140 }}>
            <span style={{ fontSize: 13, color: "#64748b", fontWeight: 500 }}>Status</span>
            <select
              className="input"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="">All statuses</option>
              <option value="pending">Pending</option>
              <option value="accepted">Accepted</option>
              <option value="rejected">Rejected</option>
              <option value="overridden">Overridden</option>
            </select>
          </label>

          <Button variant="secondary" loading={loading} onClick={() => void fetchPage(page)}>
            Refresh
          </Button>
        </div>
      </Card>

      {/* Evaluations Table */}
      <Card>
        {loading ? (
          <p style={{ padding: 24, color: "#64748b", textAlign: "center" }}>
            Loading evaluations...
          </p>
        ) : evals.length === 0 ? (
          <div style={{ padding: 48, textAlign: "center", color: "#94a3b8" }}>
            <p style={{ fontSize: 16, fontWeight: 600 }}>No evaluations found</p>
            <p style={{ fontSize: 14 }}>
              Run evaluations from the Quality page, or adjust your filters.
            </p>
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
              <thead>
                <tr style={{ background: "#f8fafc" }}>
                  {["", "Task Pack", "Task ID", "Model", "Preference", "Confidence", "Status", "Updated", "Actions"].map(
                    (h) => (
                      <th
                        key={h}
                        style={{
                          textAlign: "left",
                          padding: "10px 8px",
                          borderBottom: "2px solid #e5e7eb",
                          fontSize: 12,
                          fontWeight: 600,
                          color: "#64748b",
                          textTransform: "uppercase",
                          letterSpacing: "0.03em",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {h}
                      </th>
                    )
                  )}
                </tr>
              </thead>
              <tbody>
                {evals.map((ev) => {
                  const ejson = ev.evaluation_json ?? {};
                  const prefSource = ev.human_override?.preference ?? ejson.preference;
                  const isExpanded = expandedId === ev.id;

                  return (
                    <EvalRow
                      key={ev.id}
                      ev={ev}
                      prefSource={prefSource}
                      isExpanded={isExpanded}
                      actingId={actingId}
                      packName={getPackName(ev.task_pack_id)}
                      onToggle={() => setExpandedId(isExpanded ? null : ev.id)}
                      onAccept={() => void handleDecision(ev.id, "accept")}
                      onReject={() => void handleDecision(ev.id, "reject")}
                      onOverride={() => openOverride(ev)}
                    />
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <div style={{ padding: "8px 16px" }}>
          <Pagination currentPage={page} totalPages={totalPages} onPageChange={handlePageChange} />
        </div>
      </Card>

      {/* Override Modal */}
      <Modal
        isOpen={!!overrideTarget}
        onClose={() => setOverrideTarget(null)}
        title="Override Evaluation"
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setOverrideTarget(null)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              loading={actingId === overrideTarget?.id}
              onClick={() => void submitOverride()}
            >
              Save Override
            </Button>
          </>
        }
      >
        <div style={{ display: "grid", gap: 16 }}>
          <label style={{ display: "grid", gap: 6 }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: "#334155" }}>Preference</span>
            <select
              className="input"
              value={overrideForm.preference ?? ""}
              onChange={(e) =>
                setOverrideForm((f) => ({
                  ...f,
                  preference: e.target.value ? Number(e.target.value) : null,
                }))
              }
            >
              <option value="">No change</option>
              <option value="1">Response A</option>
              <option value="2">Response B</option>
              <option value="0">Tie</option>
            </select>
          </label>

          <label style={{ display: "grid", gap: 6 }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: "#334155" }}>Reasoning</span>
            <textarea
              className="input"
              rows={4}
              value={overrideForm.reasoning ?? ""}
              onChange={(e) => setOverrideForm((f) => ({ ...f, reasoning: e.target.value }))}
              placeholder="Explain why you are overriding the LLM's judgment..."
            />
          </label>

          {overrideTarget?.evaluation_json?.dimensions && (
            <div>
              <span style={{ fontSize: 13, fontWeight: 600, color: "#334155", display: "block", marginBottom: 8 }}>
                Dimension Scores
              </span>
              <div style={{ display: "grid", gap: 8 }}>
                {Object.entries(
                  (overrideTarget.evaluation_json.dimensions as Record<string, number>) ?? {}
                ).map(([dim, score]) => (
                  <label key={dim} style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <span style={{ minWidth: 120, fontSize: 13, color: "#475569", textTransform: "capitalize" }}>
                      {dim}
                    </span>
                    <input
                      className="input"
                      type="number"
                      min={1}
                      max={10}
                      style={{ width: 70 }}
                      value={overrideForm.dimensions?.[dim] ?? score}
                      onChange={(e) =>
                        setOverrideForm((f) => ({
                          ...f,
                          dimensions: {
                            ...(f.dimensions ?? {}),
                            [dim]: Number(e.target.value),
                          },
                        }))
                      }
                    />
                  </label>
                ))}
              </div>
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
}

/* ── Evaluation Row with expandable detail ────────────────────────── */

interface EvalRowProps {
  ev: LLMEvaluation;
  prefSource: unknown;
  isExpanded: boolean;
  actingId: string | null;
  packName: string;
  onToggle: () => void;
  onAccept: () => void;
  onReject: () => void;
  onOverride: () => void;
}

const cellStyle = {
  padding: "10px 8px",
  borderBottom: "1px solid #f1f5f9",
  verticalAlign: "top" as const,
};

function EvalRow({ ev, prefSource, isExpanded, actingId, packName, onToggle, onAccept, onReject, onOverride }: EvalRowProps) {
  const ejson = ev.evaluation_json ?? {};
  const reasoning = (ev.human_override?.reasoning ?? ejson.reasoning ?? "") as string;
  const dimensions = (ev.human_override?.dimensions ?? ejson.dimensions ?? null) as Record<string, number> | null;

  return (
    <>
      <tr
        style={{
          cursor: "pointer",
          background: isExpanded ? "#f8fafc" : "#fff",
          transition: "background 0.1s",
        }}
        onClick={onToggle}
      >
        <td style={cellStyle}>
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: 24,
              height: 24,
              borderRadius: 6,
              background: "#f1f5f9",
              fontSize: 12,
              color: "#475569",
              transition: "transform 0.15s",
              transform: isExpanded ? "rotate(90deg)" : "rotate(0deg)",
            }}
          >
            ▸
          </span>
        </td>
        <td style={cellStyle}>
          <span style={{ fontSize: 12, color: "#6366f1", fontWeight: 500 }}>{packName}</span>
        </td>
        <td style={{ ...cellStyle, fontWeight: 600 }}>{ev.task_id}</td>
        <td style={cellStyle}>
          <span style={{ fontSize: 12, fontFamily: "monospace", background: "#f1f5f9", padding: "2px 6px", borderRadius: 4 }}>
            {ev.judge_model}
          </span>
        </td>
        <td style={cellStyle}>{prefLabel(prefSource)}</td>
        <td style={cellStyle}>{confidenceBar(ev.confidence)}</td>
        <td style={cellStyle}>
          <Badge variant={statusVariant(ev.status)}>{ev.status}</Badge>
        </td>
        <td style={{ ...cellStyle, whiteSpace: "nowrap", fontSize: 12, color: "#64748b" }}>
          {new Date(ev.updated_at).toLocaleString()}
        </td>
        <td style={cellStyle} onClick={(e) => e.stopPropagation()}>
          <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
            <Button size="sm" variant="secondary" onClick={onOverride}>
              Override
            </Button>
            <Button
              size="sm"
              variant="primary"
              disabled={actingId === ev.id}
              onClick={onAccept}
            >
              Accept
            </Button>
            <Button
              size="sm"
              variant="danger"
              disabled={actingId === ev.id}
              onClick={onReject}
            >
              Reject
            </Button>
          </div>
        </td>
      </tr>

      {isExpanded && (
        <tr>
          <td colSpan={9} style={{ padding: 0, background: "#f8fafc", borderBottom: "2px solid #e5e7eb" }}>
            <div style={{ padding: "16px 24px", display: "grid", gap: 16, gridTemplateColumns: dimensions ? "1fr 1fr" : "1fr" }}>
              {/* Reasoning */}
              <div>
                <h4
                  style={{
                    margin: "0 0 8px",
                    fontSize: 12,
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: "0.04em",
                    color: "#64748b",
                  }}
                >
                  Reasoning
                </h4>
                <div
                  style={{
                    background: "#fff",
                    border: "1px solid #e5e7eb",
                    borderRadius: 8,
                    padding: 14,
                    fontSize: 13,
                    lineHeight: 1.6,
                    color: "#334155",
                    whiteSpace: "pre-wrap",
                    maxHeight: 240,
                    overflowY: "auto",
                  }}
                >
                  {reasoning || "No reasoning provided."}
                </div>

                {ev.human_override && (
                  <div style={{ marginTop: 12 }}>
                    <Badge variant="warning">Human Override Applied</Badge>
                    {ev.human_override.reasoning && (
                      <div
                        style={{
                          marginTop: 8,
                          background: "#fffbeb",
                          border: "1px solid #fde68a",
                          borderRadius: 8,
                          padding: 12,
                          fontSize: 13,
                          color: "#92400e",
                          lineHeight: 1.5,
                        }}
                      >
                        <strong>Override reasoning:</strong>{" "}
                        {ev.human_override.reasoning as string}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Dimensions */}
              {dimensions && (
                <div>
                  <h4
                    style={{
                      margin: "0 0 8px",
                      fontSize: 12,
                      fontWeight: 700,
                      textTransform: "uppercase",
                      letterSpacing: "0.04em",
                      color: "#64748b",
                    }}
                  >
                    Dimension Scores
                  </h4>
                  <div
                    style={{
                      background: "#fff",
                      border: "1px solid #e5e7eb",
                      borderRadius: 8,
                      padding: 14,
                    }}
                  >
                    {Object.entries(dimensions).map(([dim, score]) => {
                      const pct = Math.round((score / 10) * 100);
                      const barColor =
                        pct >= 70 ? "#10b981" : pct >= 40 ? "#f59e0b" : "#ef4444";
                      return (
                        <div
                          key={dim}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 10,
                            marginBottom: 8,
                          }}
                        >
                          <span
                            style={{
                              minWidth: 110,
                              fontSize: 13,
                              color: "#475569",
                              fontWeight: 500,
                              textTransform: "capitalize",
                            }}
                          >
                            {dim}
                          </span>
                          <div
                            style={{
                              flex: 1,
                              height: 8,
                              borderRadius: 4,
                              background: "#e5e7eb",
                            }}
                          >
                            <div
                              style={{
                                width: `${pct}%`,
                                height: "100%",
                                borderRadius: 4,
                                background: barColor,
                                transition: "width 0.3s",
                              }}
                            />
                          </div>
                          <span
                            style={{ fontSize: 13, fontWeight: 700, color: barColor, minWidth: 32, textAlign: "right" }}
                          >
                            {score}/10
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Metadata row */}
              <div style={{ gridColumn: "1 / -1" }}>
                <div
                  style={{
                    display: "flex",
                    gap: 20,
                    flexWrap: "wrap",
                    fontSize: 12,
                    color: "#94a3b8",
                  }}
                >
                  <span>
                    Created: {new Date(ev.created_at).toLocaleString()}
                  </span>
                  <span>
                    Updated: {new Date(ev.updated_at).toLocaleString()}
                  </span>
                  <span>ID: {ev.id}</span>
                </div>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
