"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useParams } from "next/navigation";
import { toast } from "sonner";

import { api } from "@/lib/api";
import type { InferenceModelOption } from "@/lib/api";
import { useAppStore } from "@/lib/state/store";
import type { TaskItem } from "@/types";

function exportJsonl(tasks: TaskItem[], annotations: ReturnType<typeof useAppStore.getState>["annotations"]) {
  return tasks
    .map((task) =>
      JSON.stringify({
        task_id: task.id,
        type: task.type,
        prompt: task.prompt,
        annotation: annotations[task.id] || null
      })
    )
    .join("\n");
}

function exportMarkdown(tasks: TaskItem[], annotations: ReturnType<typeof useAppStore.getState>["annotations"]) {
  const lines: string[] = ["# RLHF Annotation Export", ""];
  tasks.forEach((task, index) => {
    const ann = annotations[task.id];
    lines.push(`## ${index + 1}. ${task.title}`);
    lines.push(`- Task ID: ${task.id}`);
    lines.push(`- Type: ${task.type}`);
    lines.push(`- Status: ${ann?.status || "pending"}`);
    lines.push("");
    lines.push("### Prompt");
    lines.push(task.prompt);
    lines.push("");
    lines.push("### Annotation");
    lines.push("```json");
    lines.push(JSON.stringify(ann || {}, null, 2));
    lines.push("```");
    lines.push("");
  });
  return lines.join("\n");
}

export default function TaskPage() {
  const router = useRouter();
  const params = useParams<{ taskId: string }>();
  const {
    tasks,
    annotations,
    currentTaskIndex,
    setCurrentTaskIndex,
    updateAnnotation,
    setTaskTime,
    taskTimes
  } = useAppStore();

  const [phase, setPhase] = useState<1 | 2 | 3>(1);
  const [streamingText, setStreamingText] = useState<Record<number, string>>({});
  const [streamingDone, setStreamingDone] = useState(false);
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [availableModels, setAvailableModels] = useState<InferenceModelOption[]>([]);
  const startedAtRef = useRef<number>(Date.now());
  const [showExport, setShowExport] = useState(false);

  const task = tasks[currentTaskIndex];
  const ann = task ? annotations[task.id] : undefined;

  useEffect(() => {
    if (!tasks.length) {
      router.push("/dashboard");
      return;
    }
    const idx = Number(params.taskId);
    if (Number.isFinite(idx) && idx >= 0 && idx < tasks.length && idx !== currentTaskIndex) {
      setCurrentTaskIndex(idx);
    }
    startedAtRef.current = Date.now();
  }, [tasks.length, router, currentTaskIndex, params.taskId, setCurrentTaskIndex]);

  useEffect(() => {
    async function loadModels() {
      try {
        const info = await api.inferenceModels();
        setAvailableModels(info.models);
        setSelectedModel(info.default);
      } catch {
        // inference may be unavailable in local mode
      }
    }
    void loadModels();
  }, []);

  const trackTime = useCallback(() => {
    if (!task) return;
    const seconds = Math.round((Date.now() - startedAtRef.current) / 1000);
    setTaskTime(task.id, (taskTimes[task.id] || 0) + seconds);
    startedAtRef.current = Date.now();
  }, [task, setTaskTime, taskTimes]);

  const goNext = useCallback(() => {
    trackTime();
    if (currentTaskIndex < tasks.length - 1) {
      const nextIdx = currentTaskIndex + 1;
      setCurrentTaskIndex(nextIdx);
      setPhase(1);
      setStreamingText({});
      setStreamingDone(false);
      router.replace(`/task/${nextIdx}`);
    } else {
      router.push("/dashboard");
    }
  }, [trackTime, currentTaskIndex, tasks.length, setCurrentTaskIndex, router]);

  const goPrev = useCallback(() => {
    trackTime();
    if (currentTaskIndex > 0) {
      const prevIdx = currentTaskIndex - 1;
      setCurrentTaskIndex(prevIdx);
      setPhase(1);
      setStreamingText({});
      setStreamingDone(false);
      router.replace(`/task/${prevIdx}`);
    }
  }, [trackTime, currentTaskIndex, setCurrentTaskIndex, router]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (["INPUT", "TEXTAREA", "SELECT"].includes((e.target as HTMLElement)?.tagName)) return;
      if (phase !== 3) return;
      if (e.key === "ArrowRight" || e.key.toLowerCase() === "n") goNext();
      if (e.key === "ArrowLeft" || e.key.toLowerCase() === "p") goPrev();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [phase, goNext, goPrev]);

  async function beginStreaming() {
    if (!task) return;
    setPhase(2);
    setStreamingText({});
    setStreamingDone(false);

    const useLiveInference = task.responses.every((r) => !r.text || !r.text.trim());
    if (!useLiveInference) {
      task.responses.forEach((resp, idx) => {
        const text = resp.text || "";
        let i = 0;
        const tick = () => {
          i += 3;
          setStreamingText((prev) => ({ ...prev, [idx]: text.slice(0, i) }));
          if (i < text.length) window.setTimeout(tick, 10);
          else if (idx === task.responses.length - 1) {
            setStreamingDone(true);
          }
        };
        window.setTimeout(tick, idx * 200);
      });
      return;
    }

    try {
      const modelInfo = await api.inferenceModels();
      const response = await api.inferenceStream({
        prompt: task.prompt,
        model: selectedModel || modelInfo.default
      });
      const raw = await response.text();
      const lines = raw.split("\n").filter((l) => l.startsWith("data: "));
      const full = lines
        .map((line) => line.replace("data: ", ""))
        .filter((line) => !line.includes("[DONE]"))
        .map((line) => {
          try {
            const parsed = JSON.parse(line) as { token?: string };
            return parsed.token || "";
          } catch {
            return "";
          }
        })
        .join("");
      setStreamingText({ 0: full });
      setStreamingDone(true);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Inference streaming failed");
      setStreamingDone(true);
    }
  }

  function submitTask() {
    if (!task) return;
    if (!ann?.justification || ann.justification.trim().length < 10) {
      toast.error("Add at least 10 characters in justification");
      return;
    }
    updateAnnotation(task.id, { status: "done", completedAt: new Date().toISOString() });
    goNext();
  }

  if (!task) return null;

  return (
    <main className="container">
      <header className="card" style={{ padding: 14, display: "flex", justifyContent: "space-between" }}>
        <div>
          <h2 style={{ margin: 0 }}>
            {task.title} ({currentTaskIndex + 1}/{tasks.length})
          </h2>
          <p style={{ margin: "6px 0 0", color: "var(--muted)" }}>Phase {phase} of 3</p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn" onClick={() => setShowExport((v) => !v)}>
            {showExport ? "Hide Export" : "Export"}
          </button>
          <button className="btn" onClick={() => router.push("/dashboard")}>
            Back
          </button>
        </div>
      </header>

      {showExport ? (
        <section className="card" style={{ marginTop: 12, padding: 14 }}>
          <h3 style={{ marginTop: 0 }}>Export</h3>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              className="btn"
              onClick={() => navigator.clipboard.writeText(exportMarkdown(tasks, annotations))}
            >
              Copy Markdown
            </button>
            <button className="btn" onClick={() => navigator.clipboard.writeText(exportJsonl(tasks, annotations))}>
              Copy JSONL
            </button>
          </div>
        </section>
      ) : null}

      {phase === 3 && task.guidelines && task.guidelines.length > 0 ? (
        <details className="card" style={{ marginTop: 12, padding: 14 }}>
          <summary style={{ cursor: "pointer", fontWeight: 600 }}>Annotation Guidelines</summary>
          <ul style={{ marginTop: 8, paddingLeft: 20 }}>
            {task.guidelines.map((g, i) => (
              <li key={i} style={{ marginBottom: 4, color: "var(--muted)" }}>
                {g}
              </li>
            ))}
          </ul>
        </details>
      ) : null}

      <section className="card" style={{ marginTop: 12, padding: 16 }}>
        {phase === 1 ? (
          <>
            <h3 style={{ marginTop: 0 }}>Prompt</h3>
            <p style={{ whiteSpace: "pre-wrap" }}>{task.prompt}</p>
            <button className="btn btn-primary" onClick={beginStreaming}>
              Continue to Streaming
            </button>
          </>
        ) : null}

        {phase === 2 ? (
          <>
            <h3 style={{ marginTop: 0 }}>AI Response Streaming</h3>
            {availableModels.length ? (
              <select
                className="input"
                style={{ marginBottom: 10 }}
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
              >
                {availableModels.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name} ({m.tag})
                  </option>
                ))}
              </select>
            ) : null}
            <div style={{ display: "grid", gap: 10 }}>
              {task.responses.map((response, idx) => (
                <article key={response.label} className="card" style={{ padding: 12 }}>
                  <b>{response.label}</b>
                  <p style={{ whiteSpace: "pre-wrap" }}>{streamingText[idx] || "..."}</p>
                </article>
              ))}
            </div>
            <button className="btn btn-primary" style={{ marginTop: 10 }} disabled={!streamingDone} onClick={() => setPhase(3)}>
              Review and Annotate
            </button>
          </>
        ) : null}

        {phase === 3 ? (
          <>
            <h3 style={{ marginTop: 0 }}>Review</h3>
            {task.type === "comparison" ? (
              <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
                {task.responses.map((response, idx) => (
                  <button
                    key={response.label}
                    className={`btn ${ann?.preference === idx ? "btn-primary" : ""}`}
                    onClick={() => updateAnnotation(task.id, { preference: idx, status: "active" })}
                  >
                    Choose {response.label}
                  </button>
                ))}
                <button
                  className={`btn ${ann?.preference === -1 ? "btn-primary" : ""}`}
                  onClick={() => updateAnnotation(task.id, { preference: -1, status: "active" })}
                >
                  Tie
                </button>
              </div>
            ) : null}

            {task.type === "ranking" ? (
              <div style={{ marginBottom: 12 }}>
                <p style={{ marginTop: 0, color: "var(--muted)" }}>Order responses from best to worst.</p>
                <div style={{ display: "grid", gap: 8 }}>
                  {task.responses.map((response, idx) => {
                    const rankList =
                      ann?.ranking && ann.ranking.length === task.responses.length
                        ? ann.ranking
                        : task.responses.map((_, i) => i);
                    const pos = rankList.indexOf(idx);
                    const canUp = pos > 0;
                    const canDown = pos < rankList.length - 1;
                    return (
                      <article key={response.label} className="card" style={{ padding: 10 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <b>
                            #{pos + 1} {response.label}
                          </b>
                          <div style={{ display: "flex", gap: 6 }}>
                            <button
                              className="btn"
                              disabled={!canUp}
                              onClick={() => {
                                const next = [...rankList];
                                [next[pos], next[pos - 1]] = [next[pos - 1], next[pos]];
                                updateAnnotation(task.id, { ranking: next, status: "active" });
                              }}
                            >
                              Up
                            </button>
                            <button
                              className="btn"
                              disabled={!canDown}
                              onClick={() => {
                                const next = [...rankList];
                                [next[pos], next[pos + 1]] = [next[pos + 1], next[pos]];
                                updateAnnotation(task.id, { ranking: next, status: "active" });
                              }}
                            >
                              Down
                            </button>
                          </div>
                        </div>
                      </article>
                    );
                  })}
                </div>
              </div>
            ) : null}

            {task.type === "rating" ? (
              <div style={{ marginBottom: 12 }}>
                <h4 style={{ marginTop: 0 }}>Response</h4>
                <article className="card" style={{ padding: 12 }}>
                  <p style={{ whiteSpace: "pre-wrap", margin: 0 }}>
                    {task.responses[0]?.text || streamingText[0] || ""}
                  </p>
                </article>
              </div>
            ) : null}

            {task.dimensions.map((dimension) => (
              <div key={dimension.name} style={{ marginBottom: 10 }}>
                <label style={{ display: "block", marginBottom: 6 }}>{dimension.name}</label>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {Array.from({ length: dimension.scale }).map((_, idx) => {
                    const score = idx + 1;
                    const selected = ann?.dimensions?.[dimension.name] === score;
                    return (
                      <button
                        key={score}
                        className={`btn ${selected ? "btn-primary" : ""}`}
                        onClick={() =>
                          updateAnnotation(task.id, {
                            dimensions: { ...(ann?.dimensions || {}), [dimension.name]: score },
                            status: "active"
                          })
                        }
                      >
                        {score}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}

            <textarea
              className="input"
              rows={5}
              placeholder="Write justification (minimum 10 chars)"
              value={ann?.justification || ""}
              onChange={(e) =>
                updateAnnotation(task.id, {
                  justification: e.target.value,
                  status: "active"
                })
              }
            />

            <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
              <button className="btn" onClick={goPrev} disabled={currentTaskIndex === 0}>
                Previous
              </button>
              <button className="btn" onClick={goNext}>
                Skip
              </button>
              <button className="btn btn-primary" onClick={submitTask}>
                Submit and Next
              </button>
            </div>
          </>
        ) : null}
      </section>
    </main>
  );
}
