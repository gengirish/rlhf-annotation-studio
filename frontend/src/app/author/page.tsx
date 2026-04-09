"use client";

import type { CSSProperties } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { AppShell } from "@/components/AppShell";
import { api, type TaskPackUpsertBody } from "@/lib/api";
import { useAppStore, useHasHydrated } from "@/lib/state/store";
import type { TaskDimension, TaskItem, TaskResponse, TaskType } from "@/types";

const LANGUAGES = ["python", "java", "javascript", "general"] as const;
const TASK_TYPES: TaskType[] = ["comparison", "rating", "ranking"];

type AuthorResponse = { label: string; text: string };
type AuthorDimension = { name: string; description: string; scale: number };

interface AuthorTaskForm {
  id: string;
  type: TaskType;
  title: string;
  prompt: string;
  responses: AuthorResponse[];
  dimensions: AuthorDimension[];
}

function newTaskId(): string {
  return `task-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function slugify(name: string): string {
  return (
    name
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "") || "pack"
  );
}

function emptyTask(): AuthorTaskForm {
  return {
    id: newTaskId(),
    type: "comparison",
    title: "",
    prompt: "",
    responses: [
      { label: "A", text: "" },
      { label: "B", text: "" }
    ],
    dimensions: [{ name: "quality", description: "Overall quality", scale: 5 }]
  };
}

function toTaskItem(f: AuthorTaskForm): TaskItem {
  const responses: TaskResponse[] = f.responses.map((r) => ({
    label: r.label,
    text: r.text
  }));
  const dimensions: TaskDimension[] = f.dimensions.map((d) => ({
    name: d.name,
    description: d.description,
    scale: Math.max(2, Math.floor(Number(d.scale)) || 2)
  }));
  return {
    id: f.id,
    type: f.type,
    title: f.title.trim(),
    prompt: f.prompt,
    responses,
    dimensions
  };
}

function fromTaskItem(t: TaskItem): AuthorTaskForm {
  return {
    id: t.id,
    type: t.type,
    title: t.title,
    prompt: t.prompt,
    responses: t.responses.map((r) => ({ label: r.label, text: r.text })),
    dimensions: t.dimensions.map((d) => ({
      name: d.name,
      description: d.description,
      scale: d.scale
    }))
  };
}

type PackField = "name" | "slug" | "language";

export default function AuthorPage() {
  const router = useRouter();
  const user = useAppStore((s) => s.user);
  const sessionId = useAppStore((s) => s.sessionId);
  const hydrated = useHasHydrated();

  const [packName, setPackName] = useState("");
  const [packSlug, setPackSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [description, setDescription] = useState("");
  const [language, setLanguage] = useState<string>("python");
  const [tasks, setTasks] = useState<AuthorTaskForm[]>([emptyTask()]);
  const [loadedSlug, setLoadedSlug] = useState<string | null>(null);
  const [loadSlugInput, setLoadSlugInput] = useState("");
  const [issues, setIssues] = useState<Array<{ row_index: number; row_label: string; message: string }>>([]);
  const [invalidPackFields, setInvalidPackFields] = useState<Set<PackField>>(new Set());
  const [invalidTaskRows, setInvalidTaskRows] = useState<Set<number>>(new Set());
  const [fieldIssueMap, setFieldIssueMap] = useState<Record<string, boolean>>({});
  const [saving, setSaving] = useState(false);
  const [loadingPack, setLoadingPack] = useState(false);

  useEffect(() => {
    if (hydrated && (!user || !sessionId)) {
      router.push("/auth");
    }
  }, [hydrated, user, sessionId, router]);

  useEffect(() => {
    if (slugTouched) return;
    setPackSlug(slugify(packName));
  }, [packName, slugTouched]);

  const taskPayload = useMemo(() => tasks.map(toTaskItem), [tasks]);

  const applyIssueHighlights = useCallback(
    (list: Array<{ row_index: number; message: string }>) => {
      const rows = new Set<number>();
      const fields: Record<string, boolean> = {};
      for (const issue of list) {
        const idx = issue.row_index - 1;
        if (idx >= 0) rows.add(idx);
        const m = issue.message;
        if (m.includes("title")) fields[`t-${idx}-title`] = true;
        if (m.includes("prompt")) fields[`t-${idx}-prompt`] = true;
        if (m.includes("responses")) fields[`t-${idx}-responses`] = true;
        if (m.includes("dimensions")) fields[`t-${idx}-dimensions`] = true;
        if (m.includes("type")) fields[`t-${idx}-type`] = true;
        if (m.includes("id")) fields[`t-${idx}-id`] = true;
      }
      setInvalidTaskRows(rows);
      setFieldIssueMap(fields);
    },
    []
  );

  function validatePackMeta(): Set<PackField> {
    const next = new Set<PackField>();
    if (!packName.trim()) next.add("name");
    if (!packSlug.trim()) next.add("slug");
    if (!LANGUAGES.includes(language as (typeof LANGUAGES)[number])) next.add("language");
    return next;
  }

  async function handleValidate() {
    const packBad = validatePackMeta();
    setInvalidPackFields(packBad);
    if (packBad.size > 0) {
      setIssues([]);
      setInvalidTaskRows(new Set());
      setFieldIssueMap({});
      toast.error("Fix pack fields highlighted in red");
      return;
    }
    try {
      const res = await api.validateTasks(taskPayload);
      setIssues(res.issues);
      if (res.ok) {
        setInvalidTaskRows(new Set());
        setFieldIssueMap({});
        toast.success("Validation passed");
      } else {
        applyIssueHighlights(res.issues);
        toast.error("Validation found issues");
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Validation failed");
    }
  }

  function inputStyle(invalid: boolean): CSSProperties {
    return invalid
      ? { borderColor: "var(--danger)", boxShadow: "0 0 0 1px var(--danger)" }
      : {};
  }

  async function handleSavePack() {
    const packBad = validatePackMeta();
    setInvalidPackFields(packBad);
    if (packBad.size > 0) {
      toast.error("Pack name, slug, and language are required");
      return;
    }
    try {
      const res = await api.validateTasks(taskPayload);
      setIssues(res.issues);
      if (!res.ok) {
        applyIssueHighlights(res.issues);
        toast.error("Fix validation issues before saving");
        return;
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Validation failed");
      return;
    }

    const body: TaskPackUpsertBody = {
      name: packName.trim(),
      slug: packSlug.trim(),
      description: description.trim(),
      language,
      tasks_json: taskPayload
    };

    setSaving(true);
    try {
      if (loadedSlug) {
        await api.updateTaskPack(loadedSlug, body);
        if (body.slug !== loadedSlug) setLoadedSlug(body.slug);
        toast.success("Task pack updated");
      } else {
        await api.createTaskPack(body);
        setLoadedSlug(body.slug);
        toast.success("Task pack saved");
      }
      setInvalidTaskRows(new Set());
      setFieldIssueMap({});
      setIssues([]);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function handleLoadPack() {
    const s = loadSlugInput.trim();
    if (!s) {
      toast.error("Enter a pack slug to load");
      return;
    }
    setLoadingPack(true);
    try {
      const detail = await api.getTaskPack(s);
      setPackName(detail.name);
      setPackSlug(detail.slug);
      setSlugTouched(true);
      setDescription(detail.description);
      setLanguage(detail.language || "general");
      setTasks(detail.tasks_json?.length ? detail.tasks_json.map(fromTaskItem) : [emptyTask()]);
      setLoadedSlug(detail.slug);
      setIssues([]);
      setInvalidTaskRows(new Set());
      setInvalidPackFields(new Set());
      setFieldIssueMap({});
      toast.success("Pack loaded for editing");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Load failed");
    } finally {
      setLoadingPack(false);
    }
  }

  async function handleDeletePack() {
    if (!loadedSlug) {
      toast.error("Load a pack first to delete it");
      return;
    }
    if (!window.confirm(`Delete pack "${loadedSlug}"? This cannot be undone.`)) return;
    try {
      await api.deleteTaskPack(loadedSlug);
      setLoadedSlug(null);
      setLoadSlugInput("");
      setPackName("");
      setPackSlug("");
      setSlugTouched(false);
      setDescription("");
      setLanguage("python");
      setTasks([emptyTask()]);
      setIssues([]);
      setInvalidTaskRows(new Set());
      setFieldIssueMap({});
      toast.success("Pack deleted");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Delete failed");
    }
  }

  function updateTask(index: number, patch: Partial<AuthorTaskForm>) {
    setTasks((prev) => prev.map((t, i) => (i === index ? { ...t, ...patch } : t)));
  }

  function addTask() {
    setTasks((prev) => [...prev, emptyTask()]);
  }

  function removeTask(index: number) {
    setTasks((prev) => (prev.length <= 1 ? prev : prev.filter((_, i) => i !== index)));
  }

  if (!user || !sessionId) {
    return null;
  }

  return (
    <AppShell>
      <header className="card" style={{ padding: 16, marginBottom: 18 }}>
        <h1 style={{ margin: 0 }}>Author task pack</h1>
      </header>

      <section className="card" style={{ padding: 20, marginBottom: 18 }}>
        <h2 style={{ marginTop: 0 }}>Load existing pack</h2>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "flex-end" }}>
          <label style={{ flex: "1 1 200px", display: "grid", gap: 6 }}>
            <span style={{ fontSize: 14 }}>Slug</span>
            <input
              className="input"
              value={loadSlugInput}
              onChange={(e) => setLoadSlugInput(e.target.value)}
              placeholder="my-pack-slug"
            />
          </label>
          <button type="button" className="btn" onClick={() => void handleLoadPack()} disabled={loadingPack}>
            {loadingPack ? "Loading…" : "Load"}
          </button>
          {loadedSlug ? (
            <button type="button" className="btn btn-danger" onClick={() => void handleDeletePack()}>
              Delete pack
            </button>
          ) : null}
        </div>
        {loadedSlug ? (
          <p style={{ margin: "12px 0 0", fontSize: 13, color: "var(--muted)" }}>
            Editing: <b>{loadedSlug}</b> — Save updates the server copy.
          </p>
        ) : null}
      </section>

      <section className="card" style={{ padding: 20, marginBottom: 18 }}>
        <h2 style={{ marginTop: 0 }}>Pack metadata</h2>
        <div style={{ display: "grid", gap: 14, maxWidth: 560 }}>
          <label style={{ display: "grid", gap: 6 }}>
            <span style={{ fontSize: 14 }}>Name</span>
            <input
              className="input"
              style={inputStyle(invalidPackFields.has("name"))}
              value={packName}
              onChange={(e) => setPackName(e.target.value)}
              placeholder="My comparison pack"
            />
          </label>
          <label style={{ display: "grid", gap: 6 }}>
            <span style={{ fontSize: 14 }}>Slug</span>
            <input
              className="input"
              style={inputStyle(invalidPackFields.has("slug"))}
              value={packSlug}
              onChange={(e) => {
                setSlugTouched(true);
                setPackSlug(e.target.value);
              }}
              placeholder="my-pack"
            />
          </label>
          <label style={{ display: "grid", gap: 6 }}>
            <span style={{ fontSize: 14 }}>Description</span>
            <textarea
              className="input"
              style={{ minHeight: 80 }}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What annotators will see in the catalog"
            />
          </label>
          <label style={{ display: "grid", gap: 6 }}>
            <span style={{ fontSize: 14 }}>Language</span>
            <select
              className="input"
              style={inputStyle(invalidPackFields.has("language"))}
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
            >
              {LANGUAGES.map((lang) => (
                <option key={lang} value={lang}>
                  {lang}
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>

      <section className="card" style={{ padding: 20, marginBottom: 18 }}>
        <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
          <h2 style={{ margin: 0 }}>Tasks</h2>
          <button type="button" className="btn" onClick={addTask}>
            Add task
          </button>
        </div>

        {issues.length > 0 ? (
          <div
            style={{
              marginTop: 14,
              padding: 12,
              borderRadius: 10,
              border: "1px solid #fecaca",
              background: "#fef2f2"
            }}
          >
            <p style={{ margin: "0 0 8px", fontWeight: 600 }}>Validation issues</p>
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {issues.map((issue, i) => (
                <li key={`${issue.row_index}-${i}`} style={{ marginBottom: 4 }}>
                  <b>{issue.row_label}</b>: {issue.message}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <div style={{ marginTop: 16, display: "grid", gap: 16 }}>
          {tasks.map((task, tIdx) => {
            const rowInvalid = invalidTaskRows.has(tIdx);
            return (
              <article
                key={task.id}
                className="card"
                style={{
                  padding: 16,
                  border: rowInvalid ? "2px solid var(--danger)" : "1px solid var(--border)"
                }}
              >
                <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: 8 }}>
                  <h3 style={{ margin: 0 }}>Task {tIdx + 1}</h3>
                  <button type="button" className="btn btn-danger" onClick={() => removeTask(tIdx)}>
                    Remove
                  </button>
                </div>
                <div style={{ marginTop: 12, display: "grid", gap: 12 }}>
                  <label style={{ display: "grid", gap: 6 }}>
                    <span style={{ fontSize: 13, color: "var(--muted)" }}>ID</span>
                    <input
                      className="input"
                      style={inputStyle(!!fieldIssueMap[`t-${tIdx}-id`])}
                      value={task.id}
                      onChange={(e) => updateTask(tIdx, { id: e.target.value })}
                    />
                  </label>
                  <label style={{ display: "grid", gap: 6 }}>
                    <span style={{ fontSize: 13, color: "var(--muted)" }}>Type</span>
                    <select
                      className="input"
                      style={inputStyle(!!fieldIssueMap[`t-${tIdx}-type`])}
                      value={task.type}
                      onChange={(e) => updateTask(tIdx, { type: e.target.value as TaskType })}
                    >
                      {TASK_TYPES.map((tp) => (
                        <option key={tp} value={tp}>
                          {tp}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label style={{ display: "grid", gap: 6 }}>
                    <span style={{ fontSize: 13, color: "var(--muted)" }}>Title</span>
                    <input
                      className="input"
                      style={inputStyle(!!fieldIssueMap[`t-${tIdx}-title`])}
                      value={task.title}
                      onChange={(e) => updateTask(tIdx, { title: e.target.value })}
                    />
                  </label>
                  <label style={{ display: "grid", gap: 6 }}>
                    <span style={{ fontSize: 13, color: "var(--muted)" }}>Prompt</span>
                    <textarea
                      className="input"
                      style={{ minHeight: 100, ...inputStyle(!!fieldIssueMap[`t-${tIdx}-prompt`]) }}
                      value={task.prompt}
                      onChange={(e) => updateTask(tIdx, { prompt: e.target.value })}
                    />
                  </label>

                  <div>
                    <p style={{ margin: "0 0 8px", fontWeight: 600 }}>Responses</p>
                    <div
                      style={{
                        display: "grid",
                        gap: 10,
                        padding: 10,
                        borderRadius: 10,
                        border: fieldIssueMap[`t-${tIdx}-responses`] ? "2px solid var(--danger)" : "1px dashed var(--border)"
                      }}
                    >
                      {task.responses.map((r, rIdx) => (
                        <div key={rIdx} style={{ display: "grid", gridTemplateColumns: "1fr 2fr auto", gap: 8 }}>
                          <input
                            className="input"
                            placeholder="Label"
                            value={r.label}
                            onChange={(e) => {
                              const next = [...task.responses];
                              next[rIdx] = { ...next[rIdx], label: e.target.value };
                              updateTask(tIdx, { responses: next });
                            }}
                          />
                          <input
                            className="input"
                            placeholder="Text"
                            value={r.text}
                            onChange={(e) => {
                              const next = [...task.responses];
                              next[rIdx] = { ...next[rIdx], text: e.target.value };
                              updateTask(tIdx, { responses: next });
                            }}
                          />
                          <button
                            type="button"
                            className="btn"
                            onClick={() => {
                              const next = task.responses.filter((_, i) => i !== rIdx);
                              updateTask(tIdx, { responses: next.length ? next : [{ label: "", text: "" }] });
                            }}
                          >
                            ✕
                          </button>
                        </div>
                      ))}
                      <button
                        type="button"
                        className="btn"
                        onClick={() => updateTask(tIdx, { responses: [...task.responses, { label: "", text: "" }] })}
                      >
                        Add response
                      </button>
                    </div>
                  </div>

                  <div>
                    <p style={{ margin: "0 0 8px", fontWeight: 600 }}>Dimensions</p>
                    <div
                      style={{
                        display: "grid",
                        gap: 10,
                        padding: 10,
                        borderRadius: 10,
                        border: fieldIssueMap[`t-${tIdx}-dimensions`] ? "2px solid var(--danger)" : "1px dashed var(--border)"
                      }}
                    >
                      {task.dimensions.map((d, dIdx) => (
                        <div
                          key={dIdx}
                          style={{
                            display: "grid",
                            gridTemplateColumns: "1fr 2fr 100px auto",
                            gap: 8,
                            alignItems: "end"
                          }}
                        >
                          <label style={{ display: "grid", gap: 4 }}>
                            <span style={{ fontSize: 12, color: "var(--muted)" }}>Name</span>
                            <input
                              className="input"
                              value={d.name}
                              onChange={(e) => {
                                const next = [...task.dimensions];
                                next[dIdx] = { ...next[dIdx], name: e.target.value };
                                updateTask(tIdx, { dimensions: next });
                              }}
                            />
                          </label>
                          <label style={{ display: "grid", gap: 4 }}>
                            <span style={{ fontSize: 12, color: "var(--muted)" }}>Description</span>
                            <input
                              className="input"
                              value={d.description}
                              onChange={(e) => {
                                const next = [...task.dimensions];
                                next[dIdx] = { ...next[dIdx], description: e.target.value };
                                updateTask(tIdx, { dimensions: next });
                              }}
                            />
                          </label>
                          <label style={{ display: "grid", gap: 4 }}>
                            <span style={{ fontSize: 12, color: "var(--muted)" }}>Scale</span>
                            <input
                              className="input"
                              type="number"
                              min={2}
                              value={d.scale}
                              onChange={(e) => {
                                const next = [...task.dimensions];
                                next[dIdx] = { ...next[dIdx], scale: Number(e.target.value) };
                                updateTask(tIdx, { dimensions: next });
                              }}
                            />
                          </label>
                          <button
                            type="button"
                            className="btn"
                            onClick={() => {
                              const next = task.dimensions.filter((_, i) => i !== dIdx);
                              updateTask(tIdx, {
                                dimensions: next.length ? next : [{ name: "", description: "", scale: 5 }]
                              });
                            }}
                          >
                            ✕
                          </button>
                        </div>
                      ))}
                      <button
                        type="button"
                        className="btn"
                        onClick={() =>
                          updateTask(tIdx, {
                            dimensions: [...task.dimensions, { name: "", description: "", scale: 5 }]
                          })
                        }
                      >
                        Add dimension
                      </button>
                    </div>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      <section className="card" style={{ padding: 20 }}>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
          <button type="button" className="btn" onClick={() => void handleValidate()}>
            Validate
          </button>
          <button type="button" className="btn btn-primary" onClick={() => void handleSavePack()} disabled={saving}>
            {saving ? "Saving…" : loadedSlug ? "Save pack (update)" : "Save pack"}
          </button>
        </div>
      </section>
    </AppShell>
  );
}
