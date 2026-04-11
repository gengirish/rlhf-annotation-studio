"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";

import { AppShell } from "@/components/AppShell";
import { api, ApiError, type ExamAttemptRead, type ExamRead, type TaskPackDetail } from "@/lib/api";
import { useAppStore, useHasHydrated } from "@/lib/state/store";
import type { TaskItem } from "@/types";

const INTEGRITY_THROTTLE_MS = 5000;

function parseDimensionsJson(raw: string): Record<string, number> | null {
  const t = raw.trim();
  if (!t) return {};
  try {
    const v = JSON.parse(t) as unknown;
    if (typeof v !== "object" || v === null || Array.isArray(v)) return null;
    const out: Record<string, number> = {};
    for (const [k, val] of Object.entries(v as Record<string, unknown>)) {
      if (typeof val === "number" && Number.isFinite(val)) out[k] = val;
      else return null;
    }
    return out;
  } catch {
    return null;
  }
}

function annotationFromStored(entry: unknown): {
  preference: number | "";
  justification: string;
  dimensionsJson: string;
} {
  if (!entry || typeof entry !== "object" || Array.isArray(entry)) {
    return { preference: "", justification: "", dimensionsJson: "{}" };
  }
  const o = entry as Record<string, unknown>;
  const pref = o.preference;
  const preference =
    typeof pref === "number" && Number.isFinite(pref) ? pref : ("" as const);
  const justification = typeof o.justification === "string" ? o.justification : "";
  const dims = o.dimensions;
  let dimensionsJson = "{}";
  if (dims && typeof dims === "object" && !Array.isArray(dims)) {
    try {
      dimensionsJson = JSON.stringify(dims, null, 2);
    } catch {
      dimensionsJson = "{}";
    }
  }
  return { preference: preference === "" ? "" : preference, justification, dimensionsJson };
}

function buildAnnotationJson(
  task: TaskItem,
  preference: number | "",
  justification: string,
  dimensions: Record<string, number> | null
): Record<string, unknown> | null {
  if (dimensions === null) return null;
  const body: Record<string, unknown> = { justification: justification.trim(), dimensions };
  if (task.type === "comparison" && preference !== "") {
    body.preference = preference;
  }
  return body;
}

export default function ExamAttemptPage() {
  const params = useParams<{ examId: string; attemptId: string }>();
  const examId = params.examId;
  const attemptId = params.attemptId;
  const router = useRouter();
  const user = useAppStore((s) => s.user);
  const sessionId = useAppStore((s) => s.sessionId);
  const hydrated = useHasHydrated();

  const [attempt, setAttempt] = useState<ExamAttemptRead | null>(null);
  const [examMeta, setExamMeta] = useState<ExamRead | null>(null);
  const [pack, setPack] = useState<TaskPackDetail | null | undefined>(undefined);
  const [packMissing, setPackMissing] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [taskIndex, setTaskIndex] = useState(0);
  const [preference, setPreference] = useState<number | "">("");
  const [justification, setJustification] = useState("");
  const [dimensionsJson, setDimensionsJson] = useState("{}");
  const [saving, setSaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const lastIntegrityAt = useRef<Record<string, number>>({});
  const taskTimeStart = useRef<number>(Date.now());

  const tasks = pack?.tasks_json ?? [];
  const task = tasks[taskIndex] ?? null;

  const sendIntegrity = useCallback(
    (eventType: string, severity: "info" | "warn" | "high", payload_json: Record<string, unknown>) => {
      if (!examId || !attemptId || attempt?.status !== "active") return;
      const now = Date.now();
      const prev = lastIntegrityAt.current[eventType] ?? 0;
      if (now - prev < INTEGRITY_THROTTLE_MS) return;
      lastIntegrityAt.current[eventType] = now;
      void api.postExamIntegrityEvent(examId, attemptId, { event_type: eventType, severity, payload_json }).catch(() => {
        /* non-blocking */
      });
    },
    [examId, attemptId, attempt?.status]
  );

  useEffect(() => {
    const onVis = () => {
      if (document.visibilityState === "hidden") {
        sendIntegrity("tab_hidden", "warn", {});
      }
    };
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, [sendIntegrity]);

  useEffect(() => {
    const onClip = (e: ClipboardEvent) => {
      const action = e.type === "copy" ? "copy" : e.type === "cut" ? "cut" : e.type === "paste" ? "paste" : e.type;
      sendIntegrity("clipboard_action", "info", { action });
    };
    document.addEventListener("copy", onClip, true);
    document.addEventListener("cut", onClip, true);
    document.addEventListener("paste", onClip, true);
    return () => {
      document.removeEventListener("copy", onClip, true);
      document.removeEventListener("cut", onClip, true);
      document.removeEventListener("paste", onClip, true);
    };
  }, [sendIntegrity]);

  const refreshAttempt = useCallback(async () => {
    const row = await api.getExamAttempt(examId, attemptId);
    setAttempt(row);
    return row;
  }, [examId, attemptId]);

  const loadAll = useCallback(async () => {
    setLoadError(null);
    setPack(undefined);
    setPackMissing(false);
    try {
      const [att, exams] = await Promise.all([api.getExamAttempt(examId, attemptId), api.getExams()]);
      setAttempt(att);
      const meta = exams.find((e) => e.id === examId) ?? null;
      setExamMeta(meta);
      const packId = meta?.task_pack_id;
      if (!packId) {
        setPack(null);
        setPackMissing(true);
        return;
      }
      const detail = await api.getTaskPackById(packId);
      if (!detail) {
        setPack(null);
        setPackMissing(true);
      } else {
        setPack(detail);
      }
    } catch (e) {
      setLoadError(e instanceof ApiError ? e.message : "Failed to load attempt");
      setAttempt(null);
      setPack(null);
    }
  }, [examId, attemptId]);

  useEffect(() => {
    if (hydrated && (!user || !sessionId)) {
      router.push("/auth");
    }
  }, [hydrated, user, sessionId, router]);

  useEffect(() => {
    if (user && sessionId && examId && attemptId) {
      void loadAll();
    }
  }, [user, sessionId, examId, attemptId, loadAll]);

  const expiresMs = useMemo(() => {
    if (!attempt?.expires_at) return null;
    const t = new Date(attempt.expires_at).getTime();
    return Number.isFinite(t) ? t : null;
  }, [attempt?.expires_at]);

  const [nowTick, setNowTick] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNowTick(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);

  const msLeft = expiresMs !== null ? Math.max(0, expiresMs - nowTick) : null;
  const timerLabel =
    msLeft === null
      ? "—"
      : `${String(Math.floor(msLeft / 60000)).padStart(2, "0")}:${String(Math.floor((msLeft % 60000) / 1000)).padStart(2, "0")}`;

  const expiryHandled = useRef(false);
  useEffect(() => {
    expiryHandled.current = false;
  }, [examId, attemptId]);

  useEffect(() => {
    if (msLeft !== 0 || !attempt || attempt.status !== "active") return;
    if (expiryHandled.current) return;
    expiryHandled.current = true;
    void (async () => {
      try {
        const row = await refreshAttempt();
        if (row.status === "timed_out") {
          toast.message("Time expired", { description: "This attempt was closed when the timer reached zero." });
        }
      } catch {
        expiryHandled.current = false;
      }
    })();
  }, [msLeft, attempt, refreshAttempt]);

  useEffect(() => {
    taskTimeStart.current = Date.now();
  }, [taskIndex, task?.id]);

  useEffect(() => {
    if (!task) return;
    const raw = attempt?.answers_json?.[task.id];
    const parsed = annotationFromStored(raw);
    setPreference(parsed.preference);
    setJustification(parsed.justification);
    setDimensionsJson(parsed.dimensionsJson);
  }, [task, attempt?.answers_json]);

  async function saveCurrentAnswer() {
    if (!task || !attempt || attempt.status !== "active") return;
    const dims = parseDimensionsJson(dimensionsJson);
    if (dims === null) {
      toast.error("Dimensions must be a JSON object with numeric values only.");
      return;
    }
    const annotation = buildAnnotationJson(task, preference, justification, dims);
    if (!annotation) return;
    const elapsed = Math.max(0, (Date.now() - taskTimeStart.current) / 1000);
    setSaving(true);
    try {
      const row = await api.saveExamAnswer(examId, attemptId, {
        task_id: task.id,
        annotation_json: annotation,
        time_spent_seconds: elapsed
      });
      setAttempt(row);
      taskTimeStart.current = Date.now();
      toast.success("Answer saved");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function submitExam() {
    if (!attempt || attempt.status !== "active") return;
    setSubmitting(true);
    try {
      await api.submitExamAttempt(examId, attemptId);
      router.push(`/exams/${examId}/result/${attemptId}`);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Submit failed");
    } finally {
      setSubmitting(false);
    }
  }

  if (!user || !sessionId) {
    return (
      <main className="container" style={{ paddingTop: 40 }}>
        <p style={{ color: "var(--muted)" }}>Redirecting to authentication…</p>
      </main>
    );
  }

  if (loadError) {
    return (
      <AppShell>
        <div className="container">
          <p style={{ color: "var(--danger)" }}>{loadError}</p>
          <Link href="/exams" className="btn" style={{ marginTop: 12, display: "inline-block" }}>
            Back to exams
          </Link>
        </div>
      </AppShell>
    );
  }

  if (!attempt) {
    return (
      <AppShell>
        <div className="container">
          <p style={{ color: "var(--muted)" }}>Loading attempt…</p>
        </div>
      </AppShell>
    );
  }

  const readOnly = attempt.status !== "active";
  const showTaskRunner = pack !== undefined && !packMissing && tasks.length > 0;

  return (
    <AppShell>
      <div className="container">
        <div style={{ marginBottom: 16 }}>
          <Link href="/exams" style={{ color: "var(--primary)", fontSize: 14 }}>
            ← Exams
          </Link>
        </div>

        <div className="card" style={{ padding: 20, marginBottom: 16 }}>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 12, justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <h1 style={{ margin: "0 0 6px", fontSize: 22 }}>{examMeta?.title ?? "Exam attempt"}</h1>
              <div style={{ fontSize: 14, color: "var(--muted)" }}>
                Status: <strong>{attempt.status}</strong>
                {attempt.score != null ? (
                  <>
                    {" "}
                    · Score {(attempt.score * 100).toFixed(1)}%
                  </>
                ) : null}
              </div>
            </div>
            <div
              style={{
                fontFamily: "ui-monospace, monospace",
                fontSize: 20,
                fontWeight: 700,
                padding: "8px 14px",
                borderRadius: 10,
                border: "1px solid var(--border)",
                background: msLeft === 0 ? "#fef2f2" : "var(--card)"
              }}
            >
              {readOnly ? "Timer stopped" : `Time left ${timerLabel}`}
            </div>
          </div>
        </div>

        {pack === undefined ? (
          <p style={{ color: "var(--muted)" }}>Loading tasks…</p>
        ) : packMissing || !pack ? (
          <div className="card" style={{ padding: 20, marginBottom: 16 }}>
            <h2 style={{ marginTop: 0 }}>Task content unavailable</h2>
            <p style={{ color: "var(--muted)", marginBottom: 0 }}>
              The exam&apos;s task pack could not be loaded (it may be missing from your org catalog or IDs may not match).
              You can still save answers if you know task IDs from your instructions; otherwise contact an administrator.
            </p>
          </div>
        ) : tasks.length === 0 ? (
          <div className="card" style={{ padding: 20 }}>
            <p style={{ margin: 0, color: "var(--muted)" }}>This pack has no tasks.</p>
          </div>
        ) : null}

        {showTaskRunner && task ? (
          <div className="card" style={{ padding: 20 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 8 }}>
              <span style={{ fontWeight: 600 }}>
                Task {taskIndex + 1} / {tasks.length}{" "}
                <span style={{ color: "var(--muted)", fontWeight: 400 }}>({task.type})</span>
              </span>
              <span style={{ fontSize: 13, color: "var(--muted)" }}>ID: {task.id}</span>
            </div>

            <h2 style={{ marginTop: 0, fontSize: 18 }}>{task.title}</h2>
            <div style={{ marginBottom: 14, padding: 12, background: "#f8fafc", borderRadius: 8, border: "1px solid var(--border)" }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: "var(--muted)", marginBottom: 4 }}>PROMPT</div>
              <p style={{ margin: 0, whiteSpace: "pre-wrap", fontSize: 14, lineHeight: 1.55 }}>{task.prompt}</p>
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns:
                  task.responses.length === 2 ? "repeat(auto-fit, minmax(min(100%, 240px), 1fr))" : "1fr",
                gap: 10,
                marginBottom: 16
              }}
            >
              {task.responses.map((response) => (
                <article key={response.label} className="card" style={{ padding: 12 }}>
                  <div style={{ fontWeight: 700, marginBottom: 6 }}>{response.label}</div>
                  <p style={{ margin: 0, whiteSpace: "pre-wrap", fontSize: 14, lineHeight: 1.55 }}>{response.text}</p>
                </article>
              ))}
            </div>

            {task.type === "comparison" ? (
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontWeight: 600, marginBottom: 8 }}>Preference (optional)</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                  <button
                    type="button"
                    className={`btn ${preference === "" ? "btn-primary" : ""}`}
                    disabled={readOnly}
                    onClick={() => setPreference("")}
                  >
                    No selection
                  </button>
                  {task.responses.map((response, idx) => (
                    <button
                      key={response.label}
                      type="button"
                      className={`btn ${preference === idx ? "btn-primary" : ""}`}
                      disabled={readOnly}
                      onClick={() => setPreference(idx)}
                    >
                      {response.label}
                    </button>
                  ))}
                  <button
                    type="button"
                    className={`btn ${preference === -1 ? "btn-primary" : ""}`}
                    disabled={readOnly}
                    onClick={() => setPreference(-1)}
                  >
                    Tie
                  </button>
                </div>
              </div>
            ) : (
              <p style={{ fontSize: 13, color: "var(--muted)" }}>
                For {task.type} tasks, use the dimensions JSON below; add free-form notes in justification if needed.
              </p>
            )}

            <label style={{ display: "block", fontWeight: 600, marginBottom: 6 }}>Justification</label>
            <textarea
              className="card"
              style={{ width: "100%", minHeight: 88, padding: 12, marginBottom: 14, border: "1px solid var(--border)", borderRadius: 8 }}
              value={justification}
              disabled={readOnly}
              onChange={(e) => setJustification(e.target.value)}
              placeholder="Explain your ratings or preference…"
            />

            <label style={{ display: "block", fontWeight: 600, marginBottom: 6 }}>
              Dimensions (JSON object: name → number)
            </label>
            <textarea
              className="card"
              style={{
                width: "100%",
                minHeight: 100,
                padding: 12,
                marginBottom: 14,
                fontFamily: "ui-monospace, monospace",
                fontSize: 13,
                border: "1px solid var(--border)",
                borderRadius: 8
              }}
              value={dimensionsJson}
              disabled={readOnly}
              onChange={(e) => setDimensionsJson(e.target.value)}
              placeholder={'{\n  "clarity": 3\n}'}
            />

            <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center" }}>
              <button type="button" className="btn" disabled={readOnly || taskIndex <= 0} onClick={() => setTaskIndex((i) => i - 1)}>
                Previous
              </button>
              <button
                type="button"
                className="btn"
                disabled={readOnly || taskIndex >= tasks.length - 1}
                onClick={() => setTaskIndex((i) => i + 1)}
              >
                Next
              </button>
              <button type="button" className="btn btn-primary" disabled={readOnly || saving} onClick={() => void saveCurrentAnswer()}>
                {saving ? "Saving…" : "Save answer"}
              </button>
              <button
                type="button"
                className="btn btn-primary"
                style={{ background: "var(--success)", borderColor: "var(--success)" }}
                disabled={readOnly || submitting}
                onClick={() => void submitExam()}
              >
                {submitting ? "Submitting…" : "Submit exam"}
              </button>
              <Link href={`/exams/${examId}/result/${attemptId}`} className="btn">
                View results
              </Link>
            </div>
          </div>
        ) : null}

        {readOnly && (
          <div className="card" style={{ padding: 16, marginTop: 16, background: "#eff6ff", borderColor: "#bfdbfe" }}>
            <p style={{ margin: 0 }}>
              This attempt is no longer editable.{" "}
              <Link href={`/exams/${examId}/result/${attemptId}`}>Open the results page</Link> for outcome details (release rules may apply).
            </p>
          </div>
        )}
      </div>
    </AppShell>
  );
}
