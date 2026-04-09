"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { AppShell } from "@/components/AppShell";
import { api, type ReviewAssignment } from "@/lib/api";
import { useAppStore, useHasHydrated } from "@/lib/state/store";

type Tab = "assignments" | "pending" | "team";

const STATUS_STYLES: Record<string, { bg: string; color: string; border: string }> = {
  assigned: { bg: "#fffbeb", color: "#b45309", border: "#f59e0b" },
  submitted: { bg: "#eff6ff", color: "#1e40af", border: "#3b82f6" },
  approved: { bg: "#ecfdf5", color: "#047857", border: "#10b981" },
  rejected: { bg: "#fef2f2", color: "#b91c1c", border: "#ef4444" }
};

function statusStyle(status: string) {
  const key = status.toLowerCase();
  return (
    STATUS_STYLES[key] ?? {
      bg: "#f8fafc",
      color: "#475569",
      border: "#e2e8f0"
    }
  );
}

function StatusBadge({ status }: { status: string }) {
  const s = statusStyle(status);
  return (
    <span
      style={{
        display: "inline-block",
        padding: "4px 10px",
        borderRadius: 999,
        fontSize: 12,
        fontWeight: 600,
        textTransform: "lowercase",
        background: s.bg,
        color: s.color,
        border: `1px solid ${s.border}`
      }}
    >
      {status}
    </span>
  );
}

function annotationSummary(annotation: Record<string, unknown> | null): string {
  if (!annotation || typeof annotation !== "object") return "—";
  const status = annotation.status;
  const justification =
    typeof annotation.justification === "string" ? annotation.justification : "";
  const dims = annotation.dimensions;
  let dimStr = "";
  if (dims && typeof dims === "object" && !Array.isArray(dims)) {
    dimStr = Object.entries(dims as Record<string, unknown>)
      .slice(0, 4)
      .map(([k, v]) => `${k}: ${String(v)}`)
      .join(", ");
  }
  const parts: string[] = [];
  if (status !== undefined) parts.push(`status: ${String(status)}`);
  if (dimStr) parts.push(dimStr);
  if (justification) parts.push(justification.slice(0, 120) + (justification.length > 120 ? "…" : ""));
  return parts.length ? parts.join(" · ") : JSON.stringify(annotation).slice(0, 160);
}

export default function ReviewsPage() {
  const router = useRouter();
  const user = useAppStore((s) => s.user);
  const sessionId = useAppStore((s) => s.sessionId);
  const hydrated = useHasHydrated();

  const [tab, setTab] = useState<Tab>("assignments");
  const [queue, setQueue] = useState<ReviewAssignment[]>([]);
  const [pending, setPending] = useState<ReviewAssignment[]>([]);
  const [teamReviews, setTeamReviews] = useState<ReviewAssignment[]>([]);
  const [loading, setLoading] = useState(true);
  const [notesById, setNotesById] = useState<Record<string, string>>({});
  const [actingId, setActingId] = useState<string | null>(null);
  const [annotatorNames, setAnnotatorNames] = useState<Record<string, string>>({});

  const canTeamReviews = user?.role === "admin" || user?.role === "reviewer";

  useEffect(() => {
    if (hydrated && (!user || !sessionId)) {
      router.push("/auth");
    }
  }, [hydrated, user, sessionId, router]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      if (tab === "team") {
        const data = await api.getTeamReviews();
        setTeamReviews(Array.isArray(data) ? data : []);
      } else {
        const [q, p] = await Promise.all([api.getReviewQueue(), api.getPendingReviews()]);
        const qList = Array.isArray(q) ? q : (q as { assignments?: ReviewAssignment[] }).assignments ?? [];
        const pList = Array.isArray(p) ? p : (p as { assignments?: ReviewAssignment[] }).assignments ?? [];
        setQueue(qList);
        setPending(pList);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load reviews");
    } finally {
      setLoading(false);
    }
  }, [tab]);

  useEffect(() => {
    if (!sessionId) return;
    if (tab === "team" && !canTeamReviews) return;
    void loadData();
  }, [sessionId, tab, canTeamReviews, loadData]);

  useEffect(() => {
    if (!user?.org_id) return;
    void api
      .getOrgMembers(user.org_id)
      .then((members) => {
        const map: Record<string, string> = {};
        members.forEach((m) => {
          map[m.id] = m.name;
        });
        setAnnotatorNames(map);
      })
      .catch(() => {
        /* optional */
      });
  }, [user?.org_id]);

  async function handleDecision(assignmentId: string, status: "approved" | "rejected") {
    const notes = notesById[assignmentId]?.trim();
    setActingId(assignmentId);
    try {
      await api.updateReview(assignmentId, {
        status,
        ...(notes ? { reviewer_notes: notes } : {})
      });
      toast.success(status === "approved" ? "Approved" : "Rejected");
      setNotesById((prev) => {
        const next = { ...prev };
        delete next[assignmentId];
        return next;
      });
      await loadData();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Update failed");
    } finally {
      setActingId(null);
    }
  }

  if (!hydrated) return null;
  if (!user || !sessionId) {
    return null;
  }

  const tabBtn = (active: boolean) =>
    ({
      padding: "10px 16px",
      borderRadius: 10,
      border: active ? "1px solid #6366f1" : "1px solid var(--border)",
      background: active ? "#eef2ff" : "#fff",
      color: active ? "#4338ca" : "var(--fg)",
      cursor: "pointer",
      fontWeight: active ? 600 : 500
    }) as const;

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
          <h1 style={{ margin: 0 }}>Review queue</h1>
          <p style={{ margin: "6px 0 0", color: "var(--muted)" }}>Assignments and pending reviews</p>
        </div>
      </header>

      <div style={{ marginTop: 18, display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button type="button" style={tabBtn(tab === "assignments")} onClick={() => setTab("assignments")}>
          My Assignments
        </button>
        <button type="button" style={tabBtn(tab === "pending")} onClick={() => setTab("pending")}>
          Pending Review
        </button>
        {canTeamReviews ? (
          <button type="button" style={tabBtn(tab === "team")} onClick={() => setTab("team")}>
            Team Reviews
          </button>
        ) : null}
      </div>

      {loading ? (
        <p style={{ marginTop: 18, color: "var(--muted)" }}>Loading…</p>
      ) : tab === "team" ? (
        <section className="card" style={{ marginTop: 18, padding: 16 }}>
          <h2 style={{ marginTop: 0 }}>Team reviews</h2>
          {teamReviews.length === 0 ? (
            <p style={{ color: "var(--muted)" }}>No team assignments.</p>
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
                  <tr>
                    <th
                      style={{
                        textAlign: "left",
                        padding: "10px 8px",
                        borderBottom: "1px solid var(--border)"
                      }}
                    >
                      Task ID
                    </th>
                    <th
                      style={{
                        textAlign: "left",
                        padding: "10px 8px",
                        borderBottom: "1px solid var(--border)"
                      }}
                    >
                      Annotator
                    </th>
                    <th
                      style={{
                        textAlign: "left",
                        padding: "10px 8px",
                        borderBottom: "1px solid var(--border)"
                      }}
                    >
                      Status
                    </th>
                    <th
                      style={{
                        textAlign: "left",
                        padding: "10px 8px",
                        borderBottom: "1px solid var(--border)"
                      }}
                    >
                      Reviewer notes
                    </th>
                    <th
                      style={{
                        textAlign: "left",
                        padding: "10px 8px",
                        borderBottom: "1px solid var(--border)"
                      }}
                    >
                      Date
                    </th>
                    <th
                      style={{
                        textAlign: "left",
                        padding: "10px 8px",
                        borderBottom: "1px solid var(--border)"
                      }}
                    />
                  </tr>
                </thead>
                <tbody>
                  {teamReviews.map((a) => {
                    const submitted = a.status.toLowerCase() === "submitted";
                    return (
                      <tr key={a.id}>
                        <td
                          style={{
                            padding: "10px 8px",
                            borderBottom: "1px solid var(--border)"
                          }}
                        >
                          {a.task_id}
                        </td>
                        <td
                          style={{
                            padding: "10px 8px",
                            borderBottom: "1px solid var(--border)"
                          }}
                        >
                          {annotatorNames[a.annotator_id] ?? a.annotator_id}
                        </td>
                        <td
                          style={{
                            padding: "10px 8px",
                            borderBottom: "1px solid var(--border)"
                          }}
                        >
                          <StatusBadge status={a.status} />
                        </td>
                        <td
                          style={{
                            padding: "10px 8px",
                            borderBottom: "1px solid var(--border)",
                            maxWidth: 280,
                            wordBreak: "break-word"
                          }}
                        >
                          {submitted ? (
                            <>
                              <textarea
                                className="input"
                                rows={2}
                                value={notesById[a.id] ?? ""}
                                onChange={(e) =>
                                  setNotesById((prev) => ({ ...prev, [a.id]: e.target.value }))
                                }
                                placeholder="Optional notes…"
                                style={{ width: "100%", resize: "vertical" }}
                              />
                              {a.reviewer_notes ? (
                                <p style={{ margin: "6px 0 0", fontSize: 12, color: "var(--muted)" }}>
                                  Existing: {a.reviewer_notes}
                                </p>
                              ) : null}
                            </>
                          ) : (
                            (a.reviewer_notes ?? "—")
                          )}
                        </td>
                        <td
                          style={{
                            padding: "10px 8px",
                            borderBottom: "1px solid var(--border)",
                            whiteSpace: "nowrap",
                            fontSize: 13,
                            color: "var(--muted)"
                          }}
                        >
                          {new Date(a.updated_at).toLocaleString()}
                        </td>
                        <td
                          style={{
                            padding: "10px 8px",
                            borderBottom: "1px solid var(--border)"
                          }}
                        >
                          {submitted ? (
                            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                              <button
                                type="button"
                                className="btn btn-primary"
                                disabled={actingId === a.id}
                                onClick={() => void handleDecision(a.id, "approved")}
                              >
                                Approve
                              </button>
                              <button
                                type="button"
                                className="btn btn-danger"
                                disabled={actingId === a.id}
                                onClick={() => void handleDecision(a.id, "rejected")}
                              >
                                Reject
                              </button>
                            </div>
                          ) : null}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      ) : tab === "assignments" ? (
        <section className="card" style={{ marginTop: 18, padding: 16 }}>
          <h2 style={{ marginTop: 0 }}>My Assignments</h2>
          {queue.length === 0 ? (
            <p style={{ color: "var(--muted)" }}>No assignments in your queue.</p>
          ) : (
            <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
              {queue.map((a) => (
                <li
                  key={a.id}
                  className="card"
                  style={{
                    padding: 14,
                    marginBottom: 10,
                    display: "flex",
                    flexWrap: "wrap",
                    alignItems: "center",
                    gap: 10,
                    justifyContent: "space-between"
                  }}
                >
                  <div>
                    <p style={{ margin: 0, fontWeight: 600 }}>Task {a.task_id}</p>
                    <p style={{ margin: "4px 0 0", fontSize: 13, color: "var(--muted)" }}>
                      Pack {a.task_pack_id} · annotator {a.annotator_id}
                    </p>
                  </div>
                  <StatusBadge status={a.status} />
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : (
        <section className="card" style={{ marginTop: 18, padding: 16 }}>
          <h2 style={{ marginTop: 0 }}>Pending Review</h2>
          {pending.length === 0 ? (
            <p style={{ color: "var(--muted)" }}>Nothing awaiting review.</p>
          ) : (
            <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
              {pending.map((a) => (
                <li key={a.id} className="card" style={{ padding: 14, marginBottom: 14 }}>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center", marginBottom: 8 }}>
                    <p style={{ margin: 0, fontWeight: 600 }}>Task {a.task_id}</p>
                    <StatusBadge status={a.status} />
                  </div>
                  <p style={{ margin: "0 0 8px", fontSize: 13, color: "var(--muted)" }}>
                    Annotator: {a.annotator_id}
                  </p>
                  <p
                    style={{
                      margin: "0 0 12px",
                      fontSize: 14,
                      lineHeight: 1.5,
                      color: "var(--fg)",
                      whiteSpace: "pre-wrap",
                      wordBreak: "break-word"
                    }}
                  >
                    {annotationSummary(a.annotation_json)}
                  </p>
                  <label style={{ display: "block", fontSize: 13, color: "var(--muted)", marginBottom: 6 }}>
                    Reviewer notes
                  </label>
                  <textarea
                    className="input"
                    rows={3}
                    value={notesById[a.id] ?? ""}
                    onChange={(e) => setNotesById((prev) => ({ ...prev, [a.id]: e.target.value }))}
                    placeholder="Optional notes for the annotator…"
                    style={{ marginBottom: 12, resize: "vertical" }}
                  />
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    <button
                      type="button"
                      className="btn btn-primary"
                      disabled={actingId === a.id}
                      onClick={() => void handleDecision(a.id, "approved")}
                    >
                      Approve
                    </button>
                    <button
                      type="button"
                      className="btn btn-danger"
                      disabled={actingId === a.id}
                      onClick={() => void handleDecision(a.id, "rejected")}
                    >
                      Reject
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </AppShell>
  );
}
