"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useParams } from "next/navigation";
import { toast } from "sonner";

import { AppShell } from "@/components/AppShell";
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

const copyBtnStyle: React.CSSProperties = {
  padding: "2px 8px",
  fontSize: 12,
  cursor: "pointer",
  border: "1px solid var(--border, #e2e8f0)",
  borderRadius: 4,
  background: "var(--bg, #fff)",
  color: "var(--muted, #64748b)",
  transition: "all .15s",
  lineHeight: "20px"
};

function CopyBtn({ text, label }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      style={copyBtnStyle}
      title={label ? `Copy ${label}` : "Copy to clipboard"}
      onClick={(e) => {
        e.stopPropagation();
        navigator.clipboard.writeText(text).then(() => {
          setCopied(true);
          toast.success(label ? `${label} copied` : "Copied!");
          setTimeout(() => setCopied(false), 1500);
        });
      }}
    >
      {copied ? "\u2713 Copied" : "\u2398 Copy"}
    </button>
  );
}

export default function TaskPage() {
  const router = useRouter();
  const params = useParams<{ taskId: string }>();
  const {
    tasks,
    annotations,
    currentTaskIndex,
    setCurrentTaskIndex,
    getNextUnfinishedTaskIndex,
    updateAnnotation,
    setTaskTime,
    taskTimes
  } = useAppStore();

  const [phase, setPhase] = useState<1 | 2 | 3>(1);
  const [streamingText, setStreamingText] = useState<Record<number, string>>({});
  const [streamingDone, setStreamingDone] = useState(false);
  const [availableModels, setAvailableModels] = useState<InferenceModelOption[]>([]);
  const [modelSlots, setModelSlots] = useState<[string, string]>(["", ""]);
  const [editablePrompt, setEditablePrompt] = useState("");
  const [inferenceLoading, setInferenceLoading] = useState(false);
  const [responseModels, setResponseModels] = useState<Record<number, string>>({});
  const startedAtRef = useRef<number>(Date.now());
  const [showExport, setShowExport] = useState(false);

  const task = tasks[currentTaskIndex];
  const ann = task ? annotations[task.id] : undefined;
  const isLiveInference = !!(task?.inference);
  const hasEditablePrompt = !!(task?.inference?.editable_prompt);

  useEffect(() => {
    if (!tasks.length) {
      router.push("/dashboard");
      return;
    }
    const idx = Number(params.taskId);
    if (!Number.isFinite(idx) || idx < 0 || idx >= tasks.length) {
      router.replace(`/task/${currentTaskIndex}`);
      return;
    }
    const taskAtRoute = tasks[idx];
    const doneAtRoute = annotations[taskAtRoute.id]?.status === "done";
    if (doneAtRoute) {
      const nextIdx = getNextUnfinishedTaskIndex(idx);
      if (nextIdx !== null) {
        setCurrentTaskIndex(nextIdx);
        router.replace(`/task/${nextIdx}`);
      } else {
        router.push("/dashboard");
      }
      return;
    }
    if (idx !== currentTaskIndex) setCurrentTaskIndex(idx);
    startedAtRef.current = Date.now();
  }, [
    tasks,
    annotations,
    router,
    currentTaskIndex,
    params.taskId,
    setCurrentTaskIndex,
    getNextUnfinishedTaskIndex
  ]);

  useEffect(() => {
    if (task) {
      setEditablePrompt(task.prompt || "");
      const m0 = task.responses[0]?.model || "";
      const m1 = task.responses[1]?.model || "";
      setModelSlots([m0, m1]);
    }
  }, [task]);

  useEffect(() => {
    async function loadModels() {
      try {
        const info = await api.inferenceModels();
        setAvailableModels(info.models);
        if (!modelSlots[0]) setModelSlots((prev) => [info.default, prev[1] || info.default]);
      } catch {
        /* inference may be unavailable */
      }
    }
    void loadModels();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const trackTime = useCallback(() => {
    if (!task) return;
    const seconds = Math.round((Date.now() - startedAtRef.current) / 1000);
    setTaskTime(task.id, (taskTimes[task.id] || 0) + seconds);
    startedAtRef.current = Date.now();
  }, [task, setTaskTime, taskTimes]);

  const goNext = useCallback(() => {
    trackTime();
    const nextIdx = getNextUnfinishedTaskIndex(currentTaskIndex);
    if (nextIdx !== null) {
      setCurrentTaskIndex(nextIdx);
      setPhase(1);
      setStreamingText({});
      setStreamingDone(false);
      setInferenceLoading(false);
      setResponseModels({});
      router.replace(`/task/${nextIdx}`);
    } else {
      router.push("/dashboard");
    }
  }, [trackTime, getNextUnfinishedTaskIndex, currentTaskIndex, setCurrentTaskIndex, router]);

  const goPrev = useCallback(() => {
    trackTime();
    if (currentTaskIndex > 0) {
      const prevIdx = currentTaskIndex - 1;
      setCurrentTaskIndex(prevIdx);
      setPhase(1);
      setStreamingText({});
      setStreamingDone(false);
      setInferenceLoading(false);
      setResponseModels({});
      router.replace(`/task/${prevIdx}`);
    }
  }, [trackTime, currentTaskIndex, setCurrentTaskIndex, router]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (["INPUT", "TEXTAREA", "SELECT"].includes((e.target as HTMLElement)?.tagName)) return;
      if (phase !== 3 || !task) return;
      if (task.type === "comparison") {
        if (e.key === "1") {
          e.preventDefault();
          updateAnnotation(task.id, { preference: 0, status: "active" });
          return;
        }
        if (e.key === "2") {
          e.preventDefault();
          updateAnnotation(task.id, { preference: 1, status: "active" });
          return;
        }
        if (e.key === "3") {
          e.preventDefault();
          updateAnnotation(task.id, { preference: -1, status: "active" });
          return;
        }
      }
      if (e.key === "ArrowRight" || e.key.toLowerCase() === "n") goNext();
      if (e.key === "ArrowLeft" || e.key.toLowerCase() === "p") goPrev();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [phase, goNext, goPrev, task, updateAnnotation]);

  async function beginStreaming() {
    if (!task) return;
    const prompt = isLiveInference ? editablePrompt.trim() : task.prompt;
    if (!prompt) {
      toast.error("Please enter a prompt");
      return;
    }

    setPhase(2);
    setStreamingText({});
    setStreamingDone(false);
    setResponseModels({});

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

    setInferenceLoading(true);
    try {
      const system = task.inference?.system || undefined;

      const slots = task.responses.map((resp, idx) => ({
        label: resp.label,
        hf_model: modelSlots[idx] || resp.model || undefined,
        seed: resp.seed,
        temperature: undefined as number | undefined
      }));

      const result = await api.inferenceComplete({ prompt, system, slots });
      const newText: Record<number, string> = {};
      const newModels: Record<number, string> = {};
      result.slots.forEach((slot, idx) => {
        if (slot.error) {
          newText[idx] = `Error: ${slot.error}`;
        } else {
          newText[idx] = slot.text || "(empty response)";
        }
        if (slot.model) newModels[idx] = slot.model;
      });

      const finalText: Record<number, string> = {};
      let charIdx = 0;
      const maxLen = Math.max(...Object.values(newText).map((t) => t.length));
      const animateTick = () => {
        charIdx += 4;
        for (const [k, v] of Object.entries(newText)) {
          finalText[Number(k)] = v.slice(0, charIdx);
        }
        setStreamingText({ ...finalText });
        if (charIdx < maxLen) {
          window.setTimeout(animateTick, 8);
        } else {
          setStreamingDone(true);
        }
      };
      setResponseModels(newModels);
      animateTick();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Inference failed");
      setStreamingDone(true);
    } finally {
      setInferenceLoading(false);
    }
  }

  function submitTask() {
    if (!task) return;
    if (!ann?.justification || ann.justification.trim().length < 10) {
      toast.error("Add at least 10 characters in justification");
      return;
    }
    if (task.type === "comparison" && ann.preference === undefined) {
      toast.error("Select a preference (A, B, or Tie)");
      return;
    }
    for (const dimension of task.dimensions) {
      const score = ann?.dimensions?.[dimension.name];
      if (score === undefined || score === null) {
        toast.error("Rate all dimensions before submitting");
        return;
      }
    }
    updateAnnotation(task.id, { status: "done", completedAt: new Date().toISOString() });
    goNext();
  }

  if (!task) return null;

  const activePrompt = isLiveInference ? editablePrompt : task.prompt;

  return (
    <AppShell>
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
              onClick={() => {
                navigator.clipboard.writeText(exportMarkdown(tasks, annotations));
                toast.success("Markdown copied");
              }}
            >
              Copy Markdown
            </button>
            <button
              className="btn"
              onClick={() => {
                navigator.clipboard.writeText(exportJsonl(tasks, annotations));
                toast.success("JSONL copied");
              }}
            >
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
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3 style={{ margin: 0 }}>Prompt</h3>
              <CopyBtn text={activePrompt} label="Prompt" />
            </div>

            {hasEditablePrompt ? (
              <>
                <textarea
                  className="input"
                  rows={5}
                  style={{ marginTop: 10, fontFamily: "inherit", fontSize: 14, width: "100%", resize: "vertical" }}
                  placeholder="Type your prompt here..."
                  value={editablePrompt}
                  onChange={(e) => setEditablePrompt(e.target.value)}
                />
                {availableModels.length >= 2 ? (
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginTop: 10 }}>
                    {task.responses.map((resp, idx) => (
                      <div key={resp.label}>
                        <label style={{ fontSize: 13, color: "var(--muted)", marginBottom: 4, display: "block" }}>
                          {resp.label} Model
                        </label>
                        <select
                          className="input"
                          style={{ width: "100%" }}
                          value={modelSlots[idx] || ""}
                          onChange={(e) =>
                            setModelSlots((prev) => {
                              const next = [...prev] as [string, string];
                              next[idx] = e.target.value;
                              return next;
                            })
                          }
                        >
                          {availableModels.map((m) => (
                            <option key={m.id} value={m.id}>
                              {m.name} ({m.tag})
                            </option>
                          ))}
                        </select>
                      </div>
                    ))}
                  </div>
                ) : null}
              </>
            ) : (
              <p style={{ whiteSpace: "pre-wrap", marginTop: 10 }}>{task.prompt}</p>
            )}

            <button
              className="btn btn-primary"
              style={{ marginTop: 12 }}
              disabled={inferenceLoading || !activePrompt.trim()}
              onClick={beginStreaming}
            >
              {isLiveInference ? "Send to Models" : "Continue to Streaming"}
            </button>
          </>
        ) : null}

        {phase === 2 ? (
          <>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3 style={{ margin: 0 }}>
                {isLiveInference ? "Live Model Responses" : "AI Response Streaming"}
              </h3>
              {inferenceLoading ? (
                <span style={{ fontSize: 13, color: "var(--muted)" }}>Generating...</span>
              ) : null}
            </div>

            {isLiveInference ? (
              <div style={{ marginTop: 8, marginBottom: 10, padding: "8px 12px", background: "var(--bg-muted, #f8fafc)", borderRadius: 6, fontSize: 13 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div>
                    <span style={{ color: "var(--muted)", fontWeight: 500 }}>Prompt: </span>
                    <span style={{ whiteSpace: "pre-wrap" }}>{activePrompt.length > 120 ? activePrompt.slice(0, 120) + "..." : activePrompt}</span>
                  </div>
                  <CopyBtn text={activePrompt} label="Prompt" />
                </div>
              </div>
            ) : null}

            <div
              style={{
                display: "grid",
                gridTemplateColumns:
                  task.responses.length === 2
                    ? "repeat(auto-fit, minmax(min(100%, 280px), 1fr))"
                    : "1fr",
                gap: 10
              }}
            >
              {task.responses.map((response, idx) => (
                <article key={response.label} className="card" style={{ padding: 12 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                    <div>
                      <b>{response.label}</b>
                      {responseModels[idx] ? (
                        <span style={{ fontSize: 12, color: "var(--muted)", marginLeft: 6 }}>
                          {availableModels.find((m) => m.id === responseModels[idx])?.name || responseModels[idx].split("/").pop()}
                        </span>
                      ) : null}
                    </div>
                    {streamingText[idx] && streamingDone ? (
                      <CopyBtn text={streamingText[idx]} label={response.label} />
                    ) : null}
                  </div>
                  <p style={{ whiteSpace: "pre-wrap", margin: 0, fontSize: 14, lineHeight: 1.6 }}>
                    {streamingText[idx] || (inferenceLoading ? "Waiting for model..." : "...")}
                  </p>
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

            <div style={{ marginBottom: 12, padding: "8px 12px", background: "var(--bg-muted, #f8fafc)", borderRadius: 6 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                <div style={{ flex: 1 }}>
                  <span style={{ fontSize: 12, fontWeight: 600, color: "var(--muted)" }}>PROMPT</span>
                  <p style={{ whiteSpace: "pre-wrap", margin: "4px 0 0", fontSize: 14 }}>{activePrompt}</p>
                </div>
                <CopyBtn text={activePrompt} label="Prompt" />
              </div>
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns:
                  task.responses.length === 2
                    ? "repeat(auto-fit, minmax(min(100%, 280px), 1fr))"
                    : "1fr",
                gap: 10,
                marginBottom: 12
              }}
            >
              {task.responses.map((response, idx) => {
                const text = streamingText[idx] || response.text || "";
                return (
                  <article key={response.label} className="card" style={{ padding: 12 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                      <div>
                        <b>{response.label}</b>
                        {responseModels[idx] ? (
                          <span style={{ fontSize: 12, color: "var(--muted)", marginLeft: 6 }}>
                            {availableModels.find((m) => m.id === responseModels[idx])?.name || responseModels[idx].split("/").pop()}
                          </span>
                        ) : null}
                      </div>
                      {text ? <CopyBtn text={text} label={response.label} /> : null}
                    </div>
                    <p style={{ whiteSpace: "pre-wrap", margin: 0, fontSize: 14, lineHeight: 1.6 }}>{text}</p>
                  </article>
                );
              })}
            </div>

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
                  <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 4 }}>
                    <CopyBtn text={task.responses[0]?.text || streamingText[0] || ""} label="Response" />
                  </div>
                  <p style={{ whiteSpace: "pre-wrap", margin: 0 }}>
                    {task.responses[0]?.text || streamingText[0] || ""}
                  </p>
                </article>
              </div>
            ) : null}

            {task.dimensions.map((dimension) => (
              <div key={dimension.name} style={{ marginBottom: 10 }}>
                <label style={{ display: "block", marginBottom: 6 }}>
                  {dimension.name}
                  {dimension.description ? (
                    <span style={{ fontWeight: 400, color: "var(--muted)", fontSize: 13, marginLeft: 6 }}>
                      — {dimension.description}
                    </span>
                  ) : null}
                </label>
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
    </AppShell>
  );
}
