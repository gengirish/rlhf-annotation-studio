"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { api, taskCatalog } from "@/lib/api";
import { useAppStore } from "@/lib/state/store";
import { fetchTaskPack } from "@/lib/task-packs";
import type { WorkspaceSnapshot } from "@/types";

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
    logout
  } = useAppStore();
  const [syncState, setSyncState] = useState<"idle" | "syncing" | "synced" | "error">("idle");

  const completed = useMemo(
    () => Object.values(annotations).filter((ann) => ann.status === "done").length,
    [annotations]
  );

  useEffect(() => {
    if (!user || !sessionId) {
      router.push("/auth");
    }
  }, [user, sessionId, router]);

  useEffect(() => {
    async function bootstrapWorkspace() {
      if (!sessionId || tasks.length > 0) return;
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

  async function loadPack(file: string) {
    try {
      const data = await fetchTaskPack(file);
      const validation = await api.validateTasks(data);
      if (!validation.ok) {
        toast.error("Selected task pack has validation issues");
        return;
      }
      loadTasks(data, `tasks/${file}`);
      toast.success(`Loaded ${data.length} tasks`);
      router.push("/task/0");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Task loading failed");
    }
  }

  return (
    <main className="container">
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
          <h1 style={{ margin: 0 }}>Welcome, {user?.name || "Annotator"}</h1>
          <p style={{ margin: "6px 0 0", color: "var(--muted)" }}>
            Session sync: <b>{syncState}</b>
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn" onClick={restoreWorkspace}>
            Restore from server
          </button>
          <button className="btn btn-danger" onClick={logout}>
            Logout
          </button>
        </div>
      </header>

      <section style={{ marginTop: 18, display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
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
      </section>

      <section className="card" style={{ marginTop: 18, padding: 16 }}>
        <h2 style={{ marginTop: 0 }}>Task Library</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 12 }}>
          {taskCatalog.map((pack) => (
            <article key={pack.file} className="card" style={{ padding: 14 }}>
              <h3 style={{ margin: "0 0 6px" }}>{pack.name}</h3>
              <p style={{ margin: "0 0 10px", color: "var(--muted)" }}>{pack.description}</p>
              <button className="btn btn-primary" onClick={() => loadPack(pack.file)}>
                Load and Start
              </button>
            </article>
          ))}
        </div>
      </section>

      {tasks.length > 0 ? (
        <section className="card" style={{ marginTop: 18, padding: 16 }}>
          <h2 style={{ marginTop: 0 }}>Resume Annotation</h2>
          <p style={{ color: "var(--muted)" }}>Continue from your current queue at any time.</p>
          <button className="btn btn-primary" onClick={() => router.push(`/task/${0}`)}>
            Open Task Workspace
          </button>
        </section>
      ) : null}
    </main>
  );
}
