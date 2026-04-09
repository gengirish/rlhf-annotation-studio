"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/api";
import type { TaskPackDetail, TaskPackSummary, TaskSearchHit, TaskSearchResponse } from "@/lib/api";
import { useAppStore, useHasHydrated } from "@/lib/state/store";
import { fetchTaskPack } from "@/lib/task-packs";
import type { TaskItem, WorkspaceSnapshot } from "@/types";

function categoryFromPack(pack: TaskPackSummary): string {
  const language = (pack.language || "general").toLowerCase();
  if (language === "python") return "Python";
  if (language === "java") return "Java";
  if (language === "javascript") return "JavaScript / TypeScript";
  if (language === "csharp-cpp") return "C# / C++";
  if (language === "multi") return "Multi-Language";
  if (language === "general") return "General / Safety";
  return language;
}

function decoratePackTasks(pack: TaskPackSummary, detail: TaskPackDetail): TaskItem[] {
  const category = categoryFromPack(pack);
  return detail.tasks_json.map((task, idx) => ({
    ...task,
    id: `${pack.slug}::${task.id}::${idx}`,
    source_task_id: task.id,
    source_pack_slug: pack.slug,
    source_pack_name: pack.name,
    source_category: category
  }));
}

export default function DashboardPage() {
  const router = useRouter();
  const {
    user,
    sessionId,
    tasks,
    annotations,
    taskTimes,
    activePackFile,
    loadTasks,
    hydrateWorkspace,
    getFirstUnfinishedTaskIndex,
    logout
  } = useAppStore();
  const hydrated = useHasHydrated();
  const [syncState, setSyncState] = useState<"idle" | "syncing" | "synced" | "error">("idle");
  const [packCatalog, setPackCatalog] = useState<TaskPackSummary[]>([]);
  const [packsLoading, setPacksLoading] = useState(true);
  const [workflowLoading, setWorkflowLoading] = useState(false);
  const [selectedTaskIndex, setSelectedTaskIndex] = useState(0);
  const [qualityScore, setQualityScore] = useState<{
    overall_accuracy: number;
    scored_tasks: number;
  } | null>(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [searchLanguage, setSearchLanguage] = useState("");
  const [searchType, setSearchType] = useState("");
  const [searchResults, setSearchResults] = useState<TaskSearchResponse | null>(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const completed = useMemo(
    () => Object.values(annotations).filter((ann) => ann.status === "done").length,
    [annotations]
  );
  const groupedCatalog = useMemo(() => {
    const groups = new Map<string, TaskPackSummary[]>();
    packCatalog.forEach((pack) => {
      const category = categoryFromPack(pack);
      groups.set(category, [...(groups.get(category) || []), pack]);
    });
    return Array.from(groups.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [packCatalog]);

  const packCategoryBySlug = useMemo(() => {
    const map = new Map<string, string>();
    packCatalog.forEach((pack) => map.set(pack.slug, categoryFromPack(pack)));
    return map;
  }, [packCatalog]);

  const categoryProgress = useMemo(() => {
    const progress = new Map<string, { done: number; total: number }>();
    tasks.forEach((task) => {
      const category = task.source_category || (activePackFile ? packCategoryBySlug.get(activePackFile) : null) || "Uncategorized";
      const entry = progress.get(category) || { done: 0, total: 0 };
      entry.total += 1;
      if (annotations[task.id]?.status === "done") entry.done += 1;
      progress.set(category, entry);
    });
    return Array.from(progress.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [tasks, annotations, activePackFile, packCategoryBySlug]);

  useEffect(() => {
    if (!tasks.length) {
      setSelectedTaskIndex(0);
      return;
    }
    const preferred = useAppStore.getState().getFirstUnfinishedTaskIndex();
    setSelectedTaskIndex((prev) => (prev >= 0 && prev < tasks.length ? prev : preferred));
  }, [tasks]);

  useEffect(() => {
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    const q = searchQuery.trim();
    if (!q) {
      setSearchResults(null);
      setSearchLoading(false);
      return;
    }
    setSearchLoading(true);
    searchTimerRef.current = setTimeout(async () => {
      try {
        const res = await api.searchTasks({
          q,
          language: searchLanguage || undefined,
          task_type: searchType || undefined,
          limit: 20,
        });
        setSearchResults(res);
      } catch {
        setSearchResults(null);
      } finally {
        setSearchLoading(false);
      }
    }, 300);
    return () => {
      if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    };
  }, [searchQuery, searchLanguage, searchType]);

  useEffect(() => {
    async function fetchQualityScore() {
      if (!sessionId || completed <= 0) {
        setQualityScore(null);
        return;
      }
      try {
        const score = await api.scoreSession(sessionId);
        setQualityScore({
          overall_accuracy: score.overall_accuracy,
          scored_tasks: score.scored_tasks
        });
      } catch {
        // silent: gold scoring may be unavailable
      }
    }
    void fetchQualityScore();
  }, [sessionId, completed]);

  useEffect(() => {
    if (hydrated && (!user || !sessionId)) {
      router.push("/auth");
    }
  }, [hydrated, user, sessionId, router]);

  useEffect(() => {
    async function loadCatalog() {
      try {
        setPackCatalog(await api.getAllTaskPacks());
      } catch {
        toast.error("Failed to load task catalog");
      } finally {
        setPacksLoading(false);
      }
    }
    void loadCatalog();
  }, []);

  const bootstrapRan = useRef(false);
  useEffect(() => {
    async function bootstrapWorkspace() {
      if (!sessionId) return;
      // Keep local workflow state authoritative if tasks are already loaded
      // (e.g., after starting category/end-to-end workflows and navigating back).
      if (tasks.length > 0) return;
      if (bootstrapRan.current) return;
      bootstrapRan.current = true;
      try {
        const server = await api.getWorkspace(sessionId);
        if ((server.tasks || []).length > 0) {
          hydrateWorkspace({
            tasks: server.tasks || [],
            annotations: server.annotations,
            task_times: server.task_times,
            active_pack_file: server.active_pack_file
          });
          setSyncState("synced");
        }
      } catch {
        // silent: local-first bootstrap
      }
    }
    void bootstrapWorkspace();
  }, [sessionId, tasks.length, hydrateWorkspace]);

  useEffect(() => {
    const sync = async () => {
      if (!sessionId) return;
      setSyncState("syncing");
      const body: WorkspaceSnapshot = {
        tasks,
        annotations,
        task_times: taskTimes,
        active_pack_file: activePackFile
      };
      try {
        await api.putWorkspace(sessionId, body);
        setSyncState("synced");
      } catch {
        setSyncState("error");
      }
    };

    if (tasks.length > 0) {
      const handle = window.setTimeout(sync, 450);
      return () => window.clearTimeout(handle);
    }
    return undefined;
  }, [tasks, annotations, taskTimes, activePackFile, sessionId]);

  async function restoreWorkspace() {
    if (!sessionId) return;
    try {
      const server = await api.getWorkspace(sessionId);
      hydrateWorkspace({
        tasks: server.tasks || [],
        annotations: server.annotations,
        task_times: server.task_times,
        active_pack_file: server.active_pack_file
      });
      toast.success("Workspace restored");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Restore failed");
    }
  }

  async function loadPack(slug: string) {
    try {
      const data = await fetchTaskPack(slug);
      const validation = await api.validateTasks(data);
      if (!validation.ok) {
        toast.error("Selected task pack has validation issues");
        return;
      }
      loadTasks(data, slug);
      toast.success(`Loaded ${data.length} tasks`);
      router.push(`/task/${useAppStore.getState().getFirstUnfinishedTaskIndex()}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Task loading failed");
    }
  }

  async function loadCategoryWorkflow(category: string, packs: TaskPackSummary[]) {
    if (packs.length === 0) return;
    setWorkflowLoading(true);
    try {
      const details = await Promise.all(packs.map((pack) => api.getTaskPack(pack.slug)));
      const combined: TaskItem[] = [];
      details.forEach((detail, idx) => {
        combined.push(...decoratePackTasks(packs[idx], detail));
      });
      loadTasks(combined, `workflow:${category.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`);
      toast.success(`Loaded ${combined.length} tasks across ${packs.length} pack(s) in ${category}`);
      router.push(`/task/${useAppStore.getState().getFirstUnfinishedTaskIndex()}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load category workflow");
    } finally {
      setWorkflowLoading(false);
    }
  }

  async function loadEndToEndWorkflow() {
    if (packCatalog.length === 0) return;
    setWorkflowLoading(true);
    try {
      const sortedPacks = [...packCatalog].sort((a, b) =>
        `${categoryFromPack(a)}::${a.name}`.localeCompare(`${categoryFromPack(b)}::${b.name}`)
      );
      const details = await Promise.all(sortedPacks.map((pack) => api.getTaskPack(pack.slug)));
      const combined: TaskItem[] = [];
      details.forEach((detail, idx) => {
        combined.push(...decoratePackTasks(sortedPacks[idx], detail));
      });
      loadTasks(combined, "workflow:end-to-end");
      toast.success(`Loaded end-to-end workflow: ${combined.length} tasks from ${sortedPacks.length} packs`);
      router.push(`/task/${useAppStore.getState().getFirstUnfinishedTaskIndex()}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load end-to-end workflow");
    } finally {
      setWorkflowLoading(false);
    }
  }

  async function loadPackAndJumpToTask(hit: TaskSearchHit) {
    try {
      const data = await fetchTaskPack(hit.pack_slug);
      loadTasks(data, hit.pack_slug);
      const targetIdx = Math.min(hit.task_index, data.length - 1);
      toast.success(`Loaded ${data.length} tasks – jumping to "${hit.task_title}"`);
      router.push(`/task/${targetIdx}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load pack");
    }
  }

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleJsonUpload = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;

      try {
        const text = await file.text();
        const parsed: unknown = JSON.parse(text);

        if (!Array.isArray(parsed) || parsed.length === 0) {
          toast.error("JSON must be a non-empty array of tasks");
          return;
        }

        const issues: string[] = [];
        (parsed as Record<string, unknown>[]).forEach((t, i) => {
          if (!t.id) issues.push(`Task ${i}: missing "id"`);
          if (!t.type) issues.push(`Task ${i}: missing "type"`);
          if (!t.title) issues.push(`Task ${i}: missing "title"`);
          if (!t.prompt) issues.push(`Task ${i}: missing "prompt"`);
          if (!Array.isArray(t.responses) || (t.responses as unknown[]).length === 0)
            issues.push(`Task ${i}: missing or empty "responses"`);
          if (!Array.isArray(t.dimensions) || (t.dimensions as unknown[]).length === 0)
            issues.push(`Task ${i}: missing or empty "dimensions"`);
        });

        if (issues.length > 0) {
          toast.error(`Validation failed:\n${issues.slice(0, 5).join("\n")}`);
          return;
        }

        const tasks = parsed as TaskItem[];
        const packName = file.name.replace(/\.json$/i, "");

        try {
          const validation = await api.validateTasks(tasks);
          if (!validation.ok) {
            toast.error(
              `Server validation: ${validation.issues?.length ?? 0} issue(s) found`
            );
            return;
          }
        } catch {
          // server validation unavailable — rely on client-side checks above
        }

        loadTasks(tasks, packName);
        toast.success(`Loaded ${tasks.length} tasks from ${file.name}`);
        router.push(`/task/${useAppStore.getState().getFirstUnfinishedTaskIndex()}`);
      } catch (err) {
        toast.error(
          err instanceof SyntaxError
            ? "Invalid JSON file"
            : err instanceof Error
              ? err.message
              : "Failed to load file"
        );
      } finally {
        if (fileInputRef.current) fileInputRef.current.value = "";
      }
    },
    [loadTasks, router]
  );

  if (!user || !sessionId) return null;

  return (
    <AppShell>
      <header
        className="card"
        style={{
          padding: 16,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 12
        }}
      >
        <div>
          <h1 style={{ margin: 0 }}>Dashboard</h1>
          <p style={{ margin: "6px 0 0", color: "var(--muted)" }}>
            Session sync: <b>{syncState}</b>
          </p>
        </div>
        <button className="btn" onClick={restoreWorkspace}>
          Restore from server
        </button>
      </header>

      <section className="card" style={{ marginTop: 18, padding: 16 }}>
        <h2 style={{ marginTop: 0 }}>Load from JSON</h2>
        <p style={{ margin: "0 0 12px", color: "var(--muted)" }}>
          Upload a local JSON file containing an array of annotation tasks.
        </p>
        <input
          ref={fileInputRef}
          type="file"
          accept=".json"
          onChange={handleJsonUpload}
          style={{ display: "none" }}
        />
        <button
          className="btn btn-primary"
          onClick={() => fileInputRef.current?.click()}
        >
          Choose JSON File
        </button>
      </section>

      <section className="card" style={{ marginTop: 18, padding: 16 }}>
        <h2 style={{ marginTop: 0 }}>Search Tasks</h2>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "flex-end" }}>
          <label style={{ display: "grid", gap: 4, flex: "1 1 280px" }}>
            <span style={{ fontSize: 13, color: "var(--muted)" }}>Search packs and tasks</span>
            <input
              className="input"
              type="text"
              placeholder="e.g. API, debugging, python, ranking..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ width: "100%" }}
            />
          </label>
          <label style={{ display: "grid", gap: 4 }}>
            <span style={{ fontSize: 13, color: "var(--muted)" }}>Language</span>
            <select className="input" value={searchLanguage} onChange={(e) => setSearchLanguage(e.target.value)}>
              <option value="">All Languages</option>
              <option value="python">Python</option>
              <option value="java">Java</option>
              <option value="javascript">JavaScript</option>
              <option value="csharp-cpp">C# / C++</option>
              <option value="multi">Multi-Language</option>
              <option value="general">General</option>
            </select>
          </label>
          <label style={{ display: "grid", gap: 4 }}>
            <span style={{ fontSize: 13, color: "var(--muted)" }}>Task Type</span>
            <select className="input" value={searchType} onChange={(e) => setSearchType(e.target.value)}>
              <option value="">All Types</option>
              <option value="comparison">Comparison</option>
              <option value="rating">Rating</option>
              <option value="ranking">Ranking</option>
            </select>
          </label>
        </div>

        {searchLoading && (
          <p style={{ marginTop: 12, color: "var(--muted)" }}>Searching...</p>
        )}

        {searchResults && !searchLoading && (
          <div style={{ marginTop: 14 }}>
            {searchResults.total_packs === 0 && searchResults.total_tasks === 0 ? (
              <p style={{ color: "var(--muted)" }}>
                No results for &ldquo;{searchResults.query}&rdquo;
              </p>
            ) : (
              <>
                {searchResults.packs.length > 0 && (
                  <div style={{ marginBottom: 14 }}>
                    <h3 style={{ margin: "0 0 8px", fontSize: 15 }}>
                      Matching Packs ({searchResults.total_packs})
                    </h3>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 10 }}>
                      {searchResults.packs.map((pack) => (
                        <article
                          key={pack.slug}
                          className="card"
                          style={{ padding: 12, display: "flex", flexDirection: "column", justifyContent: "space-between" }}
                        >
                          <div>
                            <h4 style={{ margin: "0 0 4px" }}>{pack.name}</h4>
                            <p style={{ margin: "0 0 4px", fontSize: 13, color: "var(--muted)" }}>
                              {pack.description}
                            </p>
                            <p style={{ margin: "0 0 8px", fontSize: 12, color: "var(--muted)" }}>
                              {pack.task_count} tasks &middot; {pack.language}
                            </p>
                          </div>
                          <button className="btn btn-primary" style={{ fontSize: 13 }} onClick={() => loadPack(pack.slug)}>
                            Load Pack
                          </button>
                        </article>
                      ))}
                    </div>
                  </div>
                )}
                {searchResults.tasks.length > 0 && (
                  <div>
                    <h3 style={{ margin: "0 0 8px", fontSize: 15 }}>
                      Matching Tasks ({searchResults.total_tasks})
                    </h3>
                    <div style={{ display: "grid", gap: 6 }}>
                      {searchResults.tasks.map((hit, idx) => (
                        <article
                          key={`${hit.pack_slug}-${hit.task_id}-${idx}`}
                          className="card"
                          style={{ padding: 10, display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}
                        >
                          <div style={{ minWidth: 0 }}>
                            <p style={{ margin: 0, fontWeight: 600, fontSize: 14 }}>{hit.task_title}</p>
                            <p style={{ margin: "2px 0 0", fontSize: 12, color: "var(--muted)" }}>
                              <span
                                style={{
                                  display: "inline-block",
                                  padding: "1px 6px",
                                  borderRadius: 8,
                                  fontSize: 11,
                                  marginRight: 6,
                                  background:
                                    hit.task_type === "comparison" ? "#dbeafe"
                                    : hit.task_type === "rating" ? "#fef3c7"
                                    : "#d1fae5",
                                  color:
                                    hit.task_type === "comparison" ? "#1e40af"
                                    : hit.task_type === "rating" ? "#92400e"
                                    : "#065f46",
                                }}
                              >
                                {hit.task_type}
                              </span>
                              {hit.pack_name} &middot; {hit.language} &middot; #{hit.task_index + 1}
                            </p>
                          </div>
                          <button className="btn" style={{ fontSize: 12, whiteSpace: "nowrap" }} onClick={() => loadPackAndJumpToTask(hit)}>
                            Open Task
                          </button>
                        </article>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </section>

      <section
        style={{
          marginTop: 18,
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: 12
        }}
      >
        <article className="card" style={{ padding: 14 }}>
          <h3 style={{ marginTop: 0 }}>Tasks Loaded</h3>
          <p style={{ fontSize: 26, margin: 0 }}>{tasks.length}</p>
        </article>
        <article className="card" style={{ padding: 14 }}>
          <h3 style={{ marginTop: 0 }}>Completed</h3>
          <p style={{ fontSize: 26, margin: 0 }}>{completed}</p>
        </article>
        <article className="card" style={{ padding: 14 }}>
          <h3 style={{ marginTop: 0 }}>Current Pack</h3>
          <p style={{ margin: 0, color: "var(--muted)" }}>{activePackFile || "None"}</p>
        </article>
        <article className="card" style={{ padding: 14 }}>
          <h3 style={{ marginTop: 0 }}>Quality Score</h3>
          <p style={{ fontSize: 26, margin: 0 }}>
            {qualityScore ? `${Math.round(qualityScore.overall_accuracy * 100)}%` : "—"}
          </p>
          <p style={{ margin: "4px 0 0", fontSize: 13, color: "var(--muted)" }}>
            {qualityScore ? `${qualityScore.scored_tasks} gold tasks scored` : "No gold tasks"}
          </p>
        </article>
      </section>

      <section className="card" style={{ marginTop: 18, padding: 16 }}>
        <h2 style={{ marginTop: 0 }}>Task Library</h2>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <p style={{ margin: 0, color: "var(--muted)" }}>
            Load single packs, category workflows, or a full end-to-end workflow.
          </p>
          <button className="btn btn-primary" disabled={workflowLoading || packsLoading} onClick={loadEndToEndWorkflow}>
            {workflowLoading ? "Preparing..." : "Start End-to-End Workflow"}
          </button>
        </div>
        {packsLoading ? (
          <p style={{ color: "var(--muted)" }}>Loading task packs...</p>
        ) : packCatalog.length === 0 ? (
          <p style={{ color: "var(--muted)" }}>No task packs available.</p>
        ) : (
          <div style={{ display: "grid", gap: 14 }}>
            {groupedCatalog.map(([category, packs]) => (
              <section key={category} className="card" style={{ padding: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                  <h3 style={{ margin: 0 }}>{category}</h3>
                  <button className="btn" disabled={workflowLoading} onClick={() => loadCategoryWorkflow(category, packs)}>
                    Load {category} Workflow
                  </button>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 10 }}>
                  {packs.map((pack) => (
                    <article key={pack.slug} className="card" style={{ padding: 14 }}>
                      <h4 style={{ margin: "0 0 6px" }}>{pack.name}</h4>
                      <p style={{ margin: "0 0 4px", color: "var(--muted)" }}>{pack.description}</p>
                      <p style={{ margin: "0 0 10px", fontSize: 13, color: "var(--muted)" }}>
                        {pack.task_count} tasks &middot; {pack.language}
                      </p>
                      <button className="btn btn-primary" onClick={() => loadPack(pack.slug)}>
                        Load and Start
                      </button>
                    </article>
                  ))}
                </div>
              </section>
            ))}
          </div>
        )}
      </section>

      {tasks.length > 0 ? (
        <section className="card" style={{ marginTop: 18, padding: 16 }}>
          <h2 style={{ marginTop: 0 }}>Workflow Progress by Category</h2>
          <p style={{ margin: "0 0 12px", color: "var(--muted)" }}>
            End-to-end progress is tracked across all loaded categories and task packs.
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 10 }}>
            {categoryProgress.map(([category, stat]) => {
              const pct = stat.total > 0 ? Math.round((stat.done / stat.total) * 100) : 0;
              return (
                <article key={category} className="card" style={{ padding: 12 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <b>{category}</b>
                    <span style={{ color: "var(--muted)", fontSize: 13 }}>
                      {stat.done}/{stat.total}
                    </span>
                  </div>
                  <div style={{ height: 8, marginTop: 8, background: "#e2e8f0", borderRadius: 999 }}>
                    <div
                      style={{
                        width: `${pct}%`,
                        height: "100%",
                        borderRadius: 999,
                        background: "var(--primary, #4f46e5)"
                      }}
                    />
                  </div>
                  <p style={{ margin: "8px 0 0", fontSize: 13, color: "var(--muted)" }}>{pct}% complete</p>
                </article>
              );
            })}
          </div>
        </section>
      ) : null}

      {tasks.length > 0 ? (
        <section className="card" style={{ marginTop: 18, padding: 16 }}>
          <h2 style={{ marginTop: 0 }}>Resume Annotation</h2>
          <p style={{ color: "var(--muted)" }}>
            Continue from next unfinished task or jump directly to any loaded task.
          </p>
          <div style={{ display: "grid", gap: 10, maxWidth: 760 }}>
            <label style={{ display: "grid", gap: 6 }}>
              <span style={{ fontSize: 13, color: "var(--muted)" }}>Jump to task</span>
              <select
                className="input"
                value={String(selectedTaskIndex)}
                onChange={(e) => setSelectedTaskIndex(Number(e.target.value))}
              >
                {tasks.map((task, idx) => {
                  const status = annotations[task.id]?.status || "pending";
                  const pack = task.source_pack_name || activePackFile || "loaded";
                  return (
                    <option key={task.id} value={idx}>
                      {idx + 1}. [{status}] {task.title} - {pack}
                    </option>
                  );
                })}
              </select>
            </label>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button className="btn btn-primary" onClick={() => router.push(`/task/${selectedTaskIndex}`)}>
                Open Selected Task
              </button>
              <button className="btn" onClick={() => router.push(`/task/${getFirstUnfinishedTaskIndex()}`)}>
                Continue Next Unfinished
              </button>
            </div>
          </div>
        </section>
      ) : null}
    </AppShell>
  );
}
