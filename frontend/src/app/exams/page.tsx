"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { AppShell } from "@/components/AppShell";
import { api, ApiError, type ExamRead } from "@/lib/api";
import { useAppStore, useHasHydrated } from "@/lib/state/store";

export default function ExamsPage() {
  const router = useRouter();
  const user = useAppStore((s) => s.user);
  const sessionId = useAppStore((s) => s.sessionId);
  const hydrated = useHasHydrated();
  const [exams, setExams] = useState<ExamRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [startingId, setStartingId] = useState<string | null>(null);

  const canReview = user?.role === "admin" || user?.role === "reviewer";

  useEffect(() => {
    if (hydrated && (!user || !sessionId)) {
      router.push("/auth");
    }
  }, [hydrated, user, sessionId, router]);

  const loadExams = useCallback(async () => {
    setLoading(true);
    try {
      const rows = await api.getExams();
      setExams(Array.isArray(rows) ? rows : []);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Failed to load exams");
      setExams([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user && sessionId) {
      void loadExams();
    }
  }, [user, sessionId, loadExams]);

  async function startOrResume(exam: ExamRead) {
    setStartingId(exam.id);
    try {
      const res = await api.startExamAttempt(exam.id);
      router.push(`/exams/${exam.id}/attempt/${res.id}`);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not start exam");
    } finally {
      setStartingId(null);
    }
  }

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
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
          <div>
            <h1 style={{ margin: "0 0 8px", fontSize: 28 }}>Exams</h1>
            <p style={{ margin: 0, color: "var(--muted)", maxWidth: 560 }}>
              Timed assessments linked to task packs. Start or resume your in-progress attempt from here.
            </p>
          </div>
          {canReview && (
            <Link href="/exams/review" className="btn btn-primary">
              Exam review queue
            </Link>
          )}
        </div>

        <div className="card" style={{ marginTop: 24, padding: 20 }}>
          {loading ? (
            <p style={{ margin: 0, color: "var(--muted)" }}>Loading exams…</p>
          ) : exams.length === 0 ? (
            <p style={{ margin: 0, color: "var(--muted)" }}>
              No exams are available yet. Published exams appear here for annotators; admins and reviewers also see drafts.
            </p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {exams.map((exam) => (
                <div
                  key={exam.id}
                  style={{
                    border: "1px solid var(--border)",
                    borderRadius: 10,
                    padding: 16,
                    display: "flex",
                    flexWrap: "wrap",
                    gap: 12,
                    alignItems: "center",
                    justifyContent: "space-between"
                  }}
                >
                  <div style={{ minWidth: 200, flex: 1 }}>
                    <div style={{ fontWeight: 700, fontSize: 16 }}>{exam.title}</div>
                    {exam.description ? (
                      <div style={{ marginTop: 6, color: "var(--muted)", fontSize: 14 }}>{exam.description}</div>
                    ) : null}
                    <div style={{ marginTop: 8, fontSize: 13, color: "var(--muted)" }}>
                      Duration {exam.duration_minutes} min · Pass ≥ {(exam.pass_threshold * 100).toFixed(0)}% · Up to{" "}
                      {exam.max_attempts} attempt{exam.max_attempts === 1 ? "" : "s"}
                      {!exam.is_published ? " · Draft" : ""}
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={startingId === exam.id}
                    onClick={() => void startOrResume(exam)}
                  >
                    {startingId === exam.id ? "Starting…" : "Start / resume"}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
