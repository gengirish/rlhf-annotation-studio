"use client";

import type { CSSProperties } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { AppShell } from "@/components/AppShell";
import { api, type OrgMember, type ReviewAssignment, type TaskPackSummary } from "@/lib/api";
import { useAppStore, useHasHydrated } from "@/lib/state/store";

const ROLES = ["admin", "reviewer", "annotator"] as const;

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

function statNum(stats: Record<string, number>, key: string): number {
  const v = stats[key] ?? stats[key.toLowerCase()];
  return typeof v === "number" ? v : 0;
}

export default function TeamPage() {
  const router = useRouter();
  const user = useAppStore((s) => s.user);
  const sessionId = useAppStore((s) => s.sessionId);
  const hydrated = useHasHydrated();

  const orgId = user?.org_id ?? undefined;
  const isAdmin = user?.role === "admin";
  const isReviewerOrAdmin = user?.role === "admin" || user?.role === "reviewer";

  const [members, setMembers] = useState<OrgMember[]>([]);
  const [teamStatRows, setTeamStatRows] = useState<
    Array<{ annotator: OrgMember & { role: string }; stats: Record<string, number> }>
  >([]);
  const [packs, setPacks] = useState<TaskPackSummary[]>([]);
  const [teamReviews, setTeamReviews] = useState<ReviewAssignment[]>([]);
  const [reviewStatusFilter, setReviewStatusFilter] = useState<string>("all");
  const [assignPackId, setAssignPackId] = useState("");
  const [assignAnnotatorId, setAssignAnnotatorId] = useState("");
  const [loading, setLoading] = useState(true);
  const [assigning, setAssigning] = useState(false);
  const [roleBusyId, setRoleBusyId] = useState<string | null>(null);
  const [removingId, setRemovingId] = useState<string | null>(null);
  const [reviewActingId, setReviewActingId] = useState<string | null>(null);
  const [notesById, setNotesById] = useState<Record<string, string>>({});

  const statsByAnnotatorId = useMemo(() => {
    const m = new Map<string, { annotator: OrgMember & { role: string }; stats: Record<string, number> }>();
    teamStatRows.forEach((row) => m.set(row.annotator.id, row));
    return m;
  }, [teamStatRows]);

  const annotatorNameById = useMemo(() => {
    const map: Record<string, string> = {};
    members.forEach((m) => {
      map[m.id] = m.name;
    });
    return map;
  }, [members]);

  useEffect(() => {
    if (hydrated && (!user || !sessionId)) {
      router.push("/auth");
    }
  }, [hydrated, user, sessionId, router]);

  useEffect(() => {
    if (!hydrated || !user) return;
    if (!isReviewerOrAdmin) {
      router.replace("/dashboard");
    }
  }, [hydrated, user, isReviewerOrAdmin, router]);

  const loadOrgData = useCallback(async () => {
    if (!orgId) return;
    setLoading(true);
    try {
      const [mem, stats, catalog, reviews] = await Promise.all([
        api.getOrgMembers(orgId),
        api.getTeamStats(orgId),
        api.getAllTaskPacks(),
        api.getTeamReviews(
          reviewStatusFilter === "all" ? undefined : { status: reviewStatusFilter }
        )
      ]);
      setMembers(mem);
      setTeamStatRows(stats);
      setPacks(catalog ?? []);
      setTeamReviews(Array.isArray(reviews) ? reviews : []);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load team data");
    } finally {
      setLoading(false);
    }
  }, [orgId, reviewStatusFilter]);

  useEffect(() => {
    if (!orgId || !isReviewerOrAdmin) return;
    void loadOrgData();
  }, [orgId, isReviewerOrAdmin, loadOrgData]);

  async function handleRoleChange(memberId: string, newRole: string) {
    if (!orgId || !isAdmin) return;
    setRoleBusyId(memberId);
    try {
      await api.updateMemberRole(orgId, memberId, newRole);
      toast.success("Role updated");
      await loadOrgData();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Role update failed");
    } finally {
      setRoleBusyId(null);
    }
  }

  async function handleRemoveMember(memberId: string, memberName: string) {
    if (!orgId || !isAdmin) return;
    if (!confirm(`Remove ${memberName} from the organization? They will be deactivated and lose access.`)) return;
    setRemovingId(memberId);
    try {
      await api.removeOrgMember(orgId, memberId);
      toast.success(`${memberName} has been removed`);
      await loadOrgData();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Remove failed");
    } finally {
      setRemovingId(null);
    }
  }

  async function handleBulkAssign() {
    if (!assignPackId || !assignAnnotatorId) {
      toast.error("Select a task pack and an annotator");
      return;
    }
    setAssigning(true);
    try {
      const created = await api.bulkAssign({
        task_pack_id: assignPackId,
        annotator_id: assignAnnotatorId
      });
      const n = Array.isArray(created) ? created.length : 0;
      toast.success(`Created ${n} assignment(s)`);
      await loadOrgData();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Assign failed");
    } finally {
      setAssigning(false);
    }
  }

  async function handleReviewDecision(assignmentId: string, status: "approved" | "rejected") {
    const notes = notesById[assignmentId]?.trim();
    setReviewActingId(assignmentId);
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
      await loadOrgData();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Update failed");
    } finally {
      setReviewActingId(null);
    }
  }

  if (!user || !sessionId) {
    return null;
  }

  if (!isReviewerOrAdmin) {
    return null;
  }

  if (!orgId) {
    return (
      <AppShell>
        <header className="card" style={{ padding: 16, marginBottom: 18 }}>
          <h1 style={{ margin: 0 }}>Team management</h1>
          <p style={{ margin: "8px 0 0", color: "var(--muted)" }}>
            Create an organization in Settings first.
          </p>
          <Link href="/settings" className="btn btn-primary" style={{ marginTop: 12, display: "inline-block" }}>
            Settings
          </Link>
        </header>
      </AppShell>
    );
  }

  const tableStyle: CSSProperties = {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: 14
  };
  const thtd: CSSProperties = {
    textAlign: "left",
    padding: "10px 8px",
    borderBottom: "1px solid var(--border)"
  };

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
          gap: 12,
          marginBottom: 18
        }}
      >
        <div>
          <h1 style={{ margin: 0 }}>Team management</h1>
          <p style={{ margin: "6px 0 0", color: "var(--muted)" }}>Members, assignments, and team reviews</p>
        </div>
      </header>

      {loading ? (
        <p style={{ color: "var(--muted)" }}>Loading…</p>
      ) : (
        <>
          <section className="card" style={{ padding: 16, marginBottom: 18 }}>
            <h2 style={{ marginTop: 0 }}>Team members</h2>
            <div style={{ overflowX: "auto" }}>
              <table style={tableStyle}>
                <thead>
                  <tr>
                    <th style={thtd}>Name</th>
                    <th style={thtd}>Email</th>
                    <th style={thtd}>Role</th>
                    <th style={thtd}>Assigned</th>
                    <th style={thtd}>Submitted</th>
                    <th style={thtd}>Approved</th>
                    <th style={thtd}>Rejected</th>
                    {isAdmin ? <th style={thtd}>Actions</th> : null}
                  </tr>
                </thead>
                <tbody>
                  {members.map((m) => {
                    const row = statsByAnnotatorId.get(m.id);
                    const role = row?.annotator.role ?? m.role ?? "annotator";
                    const stats = row?.stats ?? {};
                    return (
                      <tr key={m.id}>
                        <td style={thtd}>{m.name}</td>
                        <td style={thtd}>{m.email}</td>
                        <td style={thtd}>
                          {isAdmin ? (
                            <select
                              className="input"
                              value={role}
                              disabled={roleBusyId === m.id}
                              onChange={(e) => void handleRoleChange(m.id, e.target.value)}
                              style={{ minWidth: 120 }}
                            >
                              {ROLES.map((r) => (
                                <option key={r} value={r}>
                                  {r}
                                </option>
                              ))}
                            </select>
                          ) : (
                            role
                          )}
                        </td>
                        <td style={thtd}>{statNum(stats, "assigned")}</td>
                        <td style={thtd}>{statNum(stats, "submitted")}</td>
                        <td style={thtd}>{statNum(stats, "approved")}</td>
                        <td style={thtd}>{statNum(stats, "rejected")}</td>
                        {isAdmin ? (
                          <td style={thtd}>
                            {m.id !== user?.id ? (
                              <button
                                type="button"
                                className="btn btn-danger"
                                style={{ fontSize: 12, padding: "4px 10px" }}
                                disabled={removingId === m.id}
                                onClick={() => void handleRemoveMember(m.id, m.name)}
                              >
                                {removingId === m.id ? "Removing…" : "Remove"}
                              </button>
                            ) : (
                              <span style={{ fontSize: 12, color: "var(--muted)" }}>You</span>
                            )}
                          </td>
                        ) : null}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {members.length === 0 ? (
              <p style={{ color: "var(--muted)", marginBottom: 0 }}>No members in this organization.</p>
            ) : null}
          </section>

          <section className="card" style={{ padding: 16, marginBottom: 18 }}>
            <h2 style={{ marginTop: 0 }}>Assign task pack</h2>
            <p style={{ margin: "0 0 12px", color: "var(--muted)" }}>
              Bulk-assign all tasks in a pack to one annotator.
            </p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "flex-end" }}>
              <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <span style={{ fontSize: 13, color: "var(--muted)" }}>Task pack</span>
                <select
                  className="input"
                  value={assignPackId}
                  onChange={(e) => setAssignPackId(e.target.value)}
                  style={{ minWidth: 220 }}
                >
                  <option value="">Select pack…</option>
                  {packs.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <span style={{ fontSize: 13, color: "var(--muted)" }}>Annotator</span>
                <select
                  className="input"
                  value={assignAnnotatorId}
                  onChange={(e) => setAssignAnnotatorId(e.target.value)}
                  style={{ minWidth: 200 }}
                >
                  <option value="">Select annotator…</option>
                  {members.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                className="btn btn-primary"
                disabled={assigning}
                onClick={() => void handleBulkAssign()}
              >
                {assigning ? "Assigning…" : "Assign pack"}
              </button>
            </div>
          </section>

          <section className="card" style={{ padding: 16 }}>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 12, marginBottom: 16 }}>
              <h2 style={{ margin: 0 }}>Team review assignments</h2>
              <label style={{ display: "flex", alignItems: "center", gap: 8, marginLeft: "auto" }}>
                <span style={{ fontSize: 13, color: "var(--muted)" }}>Status</span>
                <select
                  className="input"
                  value={reviewStatusFilter}
                  onChange={(e) => setReviewStatusFilter(e.target.value)}
                  style={{ minWidth: 140 }}
                >
                  <option value="all">all</option>
                  <option value="assigned">assigned</option>
                  <option value="submitted">submitted</option>
                  <option value="approved">approved</option>
                  <option value="rejected">rejected</option>
                </select>
              </label>
            </div>
            {teamReviews.length === 0 ? (
              <p style={{ color: "var(--muted)" }}>No assignments match this filter.</p>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table style={tableStyle}>
                  <thead>
                    <tr>
                      <th style={thtd}>Task ID</th>
                      <th style={thtd}>Annotator</th>
                      <th style={thtd}>Status</th>
                      <th style={thtd}>Reviewer notes</th>
                      <th style={thtd}>Date</th>
                      <th style={thtd} />
                    </tr>
                  </thead>
                  <tbody>
                    {teamReviews.map((a) => {
                      const submitted = a.status.toLowerCase() === "submitted";
                      return (
                        <tr key={a.id}>
                          <td style={thtd}>{a.task_id}</td>
                          <td style={thtd}>{annotatorNameById[a.annotator_id] ?? a.annotator_id}</td>
                          <td style={thtd}>
                            <StatusBadge status={a.status} />
                          </td>
                          <td style={{ ...thtd, maxWidth: 280, wordBreak: "break-word" }}>
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
                          <td style={{ ...thtd, whiteSpace: "nowrap", fontSize: 13, color: "var(--muted)" }}>
                            {new Date(a.updated_at).toLocaleString()}
                          </td>
                          <td style={thtd}>
                            {submitted && isReviewerOrAdmin ? (
                              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                                <button
                                  type="button"
                                  className="btn btn-primary"
                                  style={{ fontSize: 12, padding: "6px 10px" }}
                                  disabled={reviewActingId === a.id}
                                  onClick={() => void handleReviewDecision(a.id, "approved")}
                                >
                                  Approve
                                </button>
                                <button
                                  type="button"
                                  className="btn btn-danger"
                                  style={{ fontSize: 12, padding: "6px 10px" }}
                                  disabled={reviewActingId === a.id}
                                  onClick={() => void handleReviewDecision(a.id, "rejected")}
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
        </>
      )}
    </AppShell>
  );
}
