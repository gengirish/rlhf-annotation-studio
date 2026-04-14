"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { api, ApiError, type ExamResultRead } from "@/lib/api";
import { useAppStore, useHasHydrated } from "@/lib/state/store";

export default function ExamResultPage() {
  const params = useParams<{ examId: string; attemptId: string }>();
  const examId = params.examId;
  const attemptId = params.attemptId;
  const router = useRouter();
  const user = useAppStore((s) => s.user);
  const sessionId = useAppStore((s) => s.sessionId);
  const hydrated = useHasHydrated();

  const [result, setResult] = useState<ExamResultRead | null>(null);
  const [pendingRelease, setPendingRelease] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setPendingRelease(false);
    try {
      const row = await api.getExamAttemptResult(examId, attemptId);
      setResult(row);
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) {
        setPendingRelease(true);
        setResult(null);
      } else {
        setError(e instanceof ApiError ? e.message : "Could not load results");
        setResult(null);
      }
    } finally {
      setLoading(false);
    }
  }, [examId, attemptId]);

  useEffect(() => {
    if (hydrated && (!user || !sessionId)) {
      router.push("/auth");
    }
  }, [hydrated, user, sessionId, router]);

  useEffect(() => {
    if (user && sessionId) {
      void load();
    }
  }, [user, sessionId, load]);

  if (!user || !sessionId) {
    return (
      <main className="container" style={{ paddingTop: 40 }}>
        <p style={{ color: "var(--muted)" }}>Redirecting to authentication…</p>
      </main>
    );
  }

  return (
    <AppShell>
      <div className="container">
        <div style={{ marginBottom: 16 }}>
          <Link href="/exams" style={{ color: "var(--primary)", fontSize: 14 }}>
            ← Exams
          </Link>
        </div>

        <h1 style={{ marginTop: 0 }}>Exam results</h1>

        {loading ? (
          <p style={{ color: "var(--muted)" }}>Loading…</p>
        ) : pendingRelease ? (
          <div className="card" style={{ padding: 24, maxWidth: 560 }}>
            <h2 style={{ marginTop: 0, fontSize: 18 }}>Results pending reviewer release.</h2>
            <p style={{ color: "var(--muted)", marginBottom: 0 }}>
              Your attempt was received. Detailed scores and notes will appear here after a reviewer or administrator releases them.
            </p>
          </div>
        ) : error ? (
          <p style={{ color: "var(--danger)" }}>{error}</p>
        ) : result ? (
          <div className="card" style={{ padding: 24, maxWidth: 640 }}>
            <dl style={{ margin: 0, display: "grid", gap: 12 }}>
              <div>
                <dt style={{ fontSize: 12, color: "var(--muted)", fontWeight: 600 }}>Status</dt>
                <dd style={{ margin: "4px 0 0", fontSize: 16 }}>{result.status}</dd>
              </div>
              <div>
                <dt style={{ fontSize: 12, color: "var(--muted)", fontWeight: 600 }}>Score</dt>
                <dd style={{ margin: "4px 0 0", fontSize: 16 }}>
                  {result.score != null ? `${(result.score * 100).toFixed(1)}%` : "—"}
                </dd>
              </div>
              <div>
                <dt style={{ fontSize: 12, color: "var(--muted)", fontWeight: 600 }}>Passed</dt>
                <dd style={{ margin: "4px 0 0", fontSize: 16 }}>
                  {result.passed === null ? "—" : result.passed ? "Yes" : "No"}
                </dd>
              </div>
              <div>
                <dt style={{ fontSize: 12, color: "var(--muted)", fontWeight: 600 }}>Integrity score</dt>
                <dd style={{ margin: "4px 0 0", fontSize: 16 }}>{(result.integrity_score * 100).toFixed(0)}%</dd>
              </div>
              {result.total_gold_tasks != null ? (
                <div>
                  <dt style={{ fontSize: 12, color: "var(--muted)", fontWeight: 600 }}>Gold tasks</dt>
                  <dd style={{ margin: "4px 0 0", fontSize: 16 }}>
                    {result.scored_tasks ?? 0} scored / {result.total_gold_tasks} total
                  </dd>
                </div>
              ) : null}
              {result.rubric && result.rubric.length > 0 ? (
                <div style={{ gridColumn: "1 / -1" }}>
                  <dt style={{ fontSize: 12, color: "var(--muted)", fontWeight: 600, marginBottom: 8 }}>
                    Structured feedback
                  </dt>
                  <dd style={{ margin: 0 }}>
                    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                      {result.rubric.map((row) => (
                        <div
                          key={row.id}
                          style={{
                            border: "1px solid var(--border)",
                            borderRadius: 10,
                            padding: 12,
                            background: "var(--card, #fff)"
                          }}
                        >
                          <div style={{ fontWeight: 700, fontSize: 15 }}>{row.title}</div>
                          <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 4, lineHeight: 1.45 }}>
                            {row.description}
                          </div>
                          <div style={{ marginTop: 10, fontSize: 15 }}>
                            <span style={{ color: "var(--muted)", fontSize: 12, fontWeight: 600 }}>Rating</span>
                            <span style={{ marginLeft: 8 }}>
                              {row.score != null ? `${row.score} / 5` : "—"}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </dd>
                </div>
              ) : null}
              {result.review_notes ? (
                <div>
                  <dt style={{ fontSize: 12, color: "var(--muted)", fontWeight: 600 }}>Review notes</dt>
                  <dd style={{ margin: "4px 0 0", fontSize: 15, whiteSpace: "pre-wrap" }}>{result.review_notes}</dd>
                </div>
              ) : null}
              {result.submitted_at ? (
                <div>
                  <dt style={{ fontSize: 12, color: "var(--muted)", fontWeight: 600 }}>Submitted</dt>
                  <dd style={{ margin: "4px 0 0", fontSize: 14 }}>{new Date(result.submitted_at).toLocaleString()}</dd>
                </div>
              ) : null}
              {result.released_at ? (
                <div>
                  <dt style={{ fontSize: 12, color: "var(--muted)", fontWeight: 600 }}>Released</dt>
                  <dd style={{ margin: "4px 0 0", fontSize: 14 }}>{new Date(result.released_at).toLocaleString()}</dd>
                </div>
              ) : null}
            </dl>
            <div style={{ marginTop: 20 }}>
              <Link href={`/exams/${examId}/attempt/${attemptId}`} className="btn">
                Back to attempt
              </Link>
            </div>
          </div>
        ) : null}
      </div>
    </AppShell>
  );
}
