"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { AppShell } from "@/components/AppShell";
import { api, ApiError, type ReviewAttemptSummary } from "@/lib/api";
import { useAppStore, useHasHydrated } from "@/lib/state/store";

export default function ExamReviewPage() {
  const router = useRouter();
  const user = useAppStore((s) => s.user);
  const sessionId = useAppStore((s) => s.sessionId);
  const hydrated = useHasHydrated();
  const [rows, setRows] = useState<ReviewAttemptSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [notesById, setNotesById] = useState<Record<string, string>>({});
  const [actingId, setActingId] = useState<string | null>(null);

  const allowed = user?.role === "admin" || user?.role === "reviewer";

  useEffect(() => {
    if (hydrated && (!user || !sessionId)) {
      router.push("/auth");
    }
  }, [hydrated, user, sessionId, router]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getExamReviewAttempts();
      setRows(Array.isArray(data) ? data : []);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Failed to load review queue");
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user && sessionId && allowed) {
      void load();
    }
  }, [user, sessionId, allowed, load]);

  async function release(attemptId: string) {
    setActingId(attemptId);
    try {
      await api.releaseExamAttemptReview(attemptId, {
        release: true,
        review_notes: notesById[attemptId]?.trim() || null
      });
      toast.success("Attempt released");
      await load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Release failed");
    } finally {
      setActingId(null);
    }
  }

  if (!user || !sessionId) {
    return (
      <main className="container" style={{ paddingTop: 40 }}>
        <p style={{ color: "var(--muted)" }}>Redirecting to authentication…</p>
      </main>
    );
  }

  if (!allowed) {
    return (
      <AppShell>
        <div className="container">
          <h1 style={{ marginTop: 0 }}>Exam review</h1>
          <p style={{ color: "var(--muted)" }}>This area is limited to reviewers and administrators.</p>
          <Link href="/exams" className="btn btn-primary" style={{ marginTop: 16, display: "inline-block" }}>
            Go to exams
          </Link>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="container">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16, flexWrap: "wrap" }}>
          <div>
            <h1 style={{ margin: "0 0 8px" }}>Exam review queue</h1>
            <p style={{ margin: 0, color: "var(--muted)", maxWidth: 560 }}>
              Submitted and timed-out attempts await release before annotators can see full results.
            </p>
          </div>
          <Link href="/exams" className="btn">
            Annotator exams
          </Link>
        </div>

        <div className="card" style={{ marginTop: 24, padding: 0, overflow: "auto" }}>
          {loading ? (
            <div style={{ padding: 20, color: "var(--muted)" }}>Loading…</div>
          ) : rows.length === 0 ? (
            <div style={{ padding: 20, color: "var(--muted)" }}>No attempts are waiting for release.</div>
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
              <thead>
                <tr style={{ textAlign: "left", borderBottom: "1px solid var(--border)", background: "#f8fafc" }}>
                  <th style={{ padding: 12 }}>Exam</th>
                  <th style={{ padding: 12 }}>Annotator</th>
                  <th style={{ padding: 12 }}>Status</th>
                  <th style={{ padding: 12 }}>Score</th>
                  <th style={{ padding: 12 }}>Integrity</th>
                  <th style={{ padding: 12, minWidth: 200 }}>Reviewer notes</th>
                  <th style={{ padding: 12 }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} style={{ borderBottom: "1px solid var(--border)", verticalAlign: "top" }}>
                    <td style={{ padding: 12 }}>
                      <div style={{ fontWeight: 600 }}>{r.exam_title}</div>
                      <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 4 }}>
                        <Link href={`/exams/${r.exam_id}/result/${r.id}`}>Result</Link>
                        {" · "}
                        <Link href={`/exams/${r.exam_id}/attempt/${r.id}`}>Attempt</Link>
                      </div>
                    </td>
                    <td style={{ padding: 12 }}>{r.annotator_email ?? r.annotator_id}</td>
                    <td style={{ padding: 12 }}>{r.status}</td>
                    <td style={{ padding: 12 }}>{r.score != null ? `${(r.score * 100).toFixed(0)}%` : "—"}</td>
                    <td style={{ padding: 12 }}>{(r.integrity_score * 100).toFixed(0)}%</td>
                    <td style={{ padding: 12 }}>
                      <textarea
                        style={{
                          width: "100%",
                          minHeight: 64,
                          padding: 8,
                          borderRadius: 8,
                          border: "1px solid var(--border)",
                          font: "inherit"
                        }}
                        placeholder="Optional notes shown to the annotator…"
                        value={notesById[r.id] ?? ""}
                        onChange={(e) => setNotesById((prev) => ({ ...prev, [r.id]: e.target.value }))}
                      />
                    </td>
                    <td style={{ padding: 12 }}>
                      <button
                        type="button"
                        className="btn btn-primary"
                        disabled={Boolean(r.released_at) || actingId === r.id}
                        onClick={() => void release(r.id)}
                      >
                        {actingId === r.id ? "…" : r.released_at ? "Released" : "Release"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </AppShell>
  );
}
