"use client";

import type { Route } from "next";
import type { CSSProperties } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { courseApi } from "@/lib/course-api";
import type { CourseModuleRead, CourseSessionRead, TaskPackSummary } from "@/types/course";

const FONT =
  'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';
const INDIGO = "#6366f1";
const EMERALD = "#10b981";
const GRAY_200 = "#e5e7eb";

type TabId = "overview" | "rubric" | "questions" | "exercises" | "resources" | "tasks";

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** Minimal markdown → HTML for trusted curriculum content; escapes text before formatting. */
function renderMarkdown(md: string): string {
  if (!md.trim()) {
    return '<div style="line-height:1.7;color:#64748b">No content for this section yet.</div>';
  }
  const codeBlocks: string[] = [];
  let blockIdx = 0;
  const withHolders = md.replace(/```[\w]*\n?([\s\S]*?)```/g, (_, body) => {
    const code = String(body).replace(/\r/g, "");
    const safe = escapeHtml(code.replace(/```$/g, ""));
    codeBlocks.push(
      `<pre style="background:#1e1e1e;color:#d4d4d4;padding:16px;border-radius:8px;overflow-x:auto;font-size:0.85rem;margin:12px 0"><code>${safe}</code></pre>`
    );
    return `\n__CODEBLOCK_${blockIdx++}__\n`;
  });

  let html = escapeHtml(withHolders)
    .replace(/^### (.*)$/gm, '<h3 style="margin:16px 0 8px;font-size:1.1rem;color:#0f172a">$1</h3>')
    .replace(/^## (.*)$/gm, '<h2 style="margin:20px 0 10px;font-size:1.25rem;color:#0f172a">$1</h2>')
    .replace(/^# (.*)$/gm, '<h1 style="margin:24px 0 12px;font-size:1.5rem;color:#0f172a">$1</h1>')
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.*?)\*/g, "<em>$1</em>")
    .replace(
      /`([^`]+)`/g,
      '<code style="background:#f3f4f6;padding:2px 6px;border-radius:4px;font-size:0.9em">$1</code>'
    )
    .replace(/^- (.*)$/gm, '<li style="margin:4px 0">$1</li>')
    .replace(/^(\d+)\. (.*)$/gm, '<li style="margin:4px 0">$2</li>')
    .replace(
      /\[([^\]]+)\]\(([^)]+)\)/g,
      `<a href="$2" target="_blank" rel="noopener noreferrer" style="color:${INDIGO}">$1</a>`
    )
    .replace(/\n{2,}/g, '</p><p style="margin:8px 0">');

  codeBlocks.forEach((block, i) => {
    html = html.replace(`__CODEBLOCK_${i}__`, block);
  });

  return `<div style="line-height:1.7;color:#334155">${html}</div>`;
}

function collectSessionNumbers(modules: CourseModuleRead[]): number[] {
  const set = new Set<number>();
  for (const m of modules) {
    for (const s of m.sessions) {
      set.add(s.number);
    }
  }
  return Array.from(set).sort((a, b) => a - b);
}

export default function CourseSessionPage() {
  const params = useParams();
  const raw = params?.sessionNumber;
  const sessionNumberStr = Array.isArray(raw) ? raw[0] : raw;
  const sessionNum = sessionNumberStr ? Number.parseInt(String(sessionNumberStr), 10) : NaN;

  const [narrow, setNarrow] = useState(false);
  const [tab, setTab] = useState<TabId>("overview");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [session, setSession] = useState<CourseSessionRead | null>(null);
  const [sessionOrder, setSessionOrder] = useState<number[]>([]);
  const [overviewError, setOverviewError] = useState<string | null>(null);

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 900px)");
    setNarrow(mq.matches);
    const fn = () => setNarrow(mq.matches);
    mq.addEventListener("change", fn);
    return () => mq.removeEventListener("change", fn);
  }, []);

  const load = useCallback(async () => {
    if (Number.isNaN(sessionNum) || sessionNum < 1) {
      setError("Invalid session number.");
      setLoading(false);
      setSession(null);
      return;
    }
    setLoading(true);
    setError(null);
    setOverviewError(null);
    try {
      const overviewPromise = courseApi.getOverview().catch((e) => {
        setOverviewError(e instanceof Error ? e.message : "Could not load course map");
        return null;
      });
      const sessionPromise = courseApi.getSession(sessionNum);
      const [ov, sess] = await Promise.all([overviewPromise, sessionPromise]);
      if (ov?.modules) {
        setSessionOrder(collectSessionNumbers(ov.modules));
      } else {
        setSessionOrder([]);
      }
      setSession(sess);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to load session";
      if (msg.includes("401")) {
        setError("Sign in to view this session. Session content requires an authenticated account.");
      } else if (msg.includes("404")) {
        setError("This session was not found.");
      } else {
        setError(msg);
      }
      setSession(null);
    } finally {
      setLoading(false);
    }
  }, [sessionNum]);

  useEffect(() => {
    void load();
  }, [load]);

  const idx = useMemo(() => sessionOrder.indexOf(sessionNum), [sessionOrder, sessionNum]);
  const prevNum = idx > 0 ? sessionOrder[idx - 1] : null;
  const nextNum = idx >= 0 && idx < sessionOrder.length - 1 ? sessionOrder[idx + 1] : null;

  const tabs: { id: TabId; label: string }[] = [
    { id: "overview", label: "Overview" },
    { id: "rubric", label: "Rubric" },
    { id: "questions", label: "Questions" },
    { id: "exercises", label: "Exercises" },
    { id: "resources", label: "Resources" },
    { id: "tasks", label: "Tasks" }
  ];

  function tabButtonStyle(active: boolean): CSSProperties {
    return {
      padding: "10px 14px",
      borderRadius: 8,
      border: active ? `1px solid ${INDIGO}` : `1px solid ${GRAY_200}`,
      background: active ? "#eef2ff" : "#fff",
      color: active ? "#4338ca" : "#0f172a",
      cursor: "pointer",
      fontWeight: active ? 600 : 500,
      fontSize: 13,
      fontFamily: "inherit",
      whiteSpace: "nowrap"
    };
  }

  return (
    <AppShell>
      <style>{`
        @keyframes courseSpin {
          to { transform: rotate(360deg); }
        }
      `}</style>

      <div style={{ fontFamily: FONT, maxWidth: 900, margin: "0 auto" }}>
        {loading ? (
          <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "40px 0" }}>
            <div
              style={{
                width: 24,
                height: 24,
                border: `3px solid ${GRAY_200}`,
                borderTopColor: INDIGO,
                borderRadius: "50%",
                animation: "courseSpin 0.75s linear infinite"
              }}
            />
            <span style={{ color: "#64748b" }}>Loading session…</span>
          </div>
        ) : null}

        {error && !loading ? (
          <div
            style={{
              padding: 20,
              borderRadius: 8,
              background: "#fef2f2",
              border: "1px solid #fecaca",
              color: "#991b1b"
            }}
          >
            <p style={{ margin: "0 0 12px" }}>{error}</p>
            <Link href="/auth" style={{ color: INDIGO, fontWeight: 600 }}>
              Go to sign in
            </Link>
            {" · "}
            <Link href="/course" style={{ color: INDIGO, fontWeight: 600 }}>
              Course overview
            </Link>
          </div>
        ) : null}

        {!loading && !error && session ? (
          <>
            <nav style={{ fontSize: 13, color: "#64748b", marginBottom: 14 }}>
              <Link href="/course" style={{ color: INDIGO, textDecoration: "none" }}>
                Course
              </Link>
              <span style={{ margin: "0 6px" }}>/</span>
              <span>
                Module {session.module.number}: {session.module.title}
              </span>
              <span style={{ margin: "0 6px" }}>/</span>
              <span style={{ color: "#0f172a", fontWeight: 600 }}>Session {session.number}</span>
            </nav>

            <h1 style={{ margin: "0 0 8px", fontSize: narrow ? 24 : 28, fontWeight: 700, color: "#0f172a" }}>
              {session.title}
            </h1>
            <p style={{ margin: "0 0 20px", fontSize: 14, color: "#64748b" }}>
              <span>{session.duration}</span>
              <span style={{ margin: "0 10px", color: GRAY_200 }}>|</span>
              <span>{session.objectives_json?.length ?? 0} learning objectives</span>
            </p>

            <div
              style={{
                display: "flex",
                gap: 8,
                flexWrap: "wrap",
                marginBottom: 20,
                paddingBottom: 4,
                borderBottom: `1px solid ${GRAY_200}`
              }}
            >
              {tabs.map((t) => (
                <button key={t.id} type="button" style={tabButtonStyle(tab === t.id)} onClick={() => setTab(t.id)}>
                  {t.label}
                </button>
              ))}
            </div>

            <section
              style={{
                background: "#fff",
                border: `1px solid ${GRAY_200}`,
                borderRadius: 8,
                boxShadow: "0 1px 2px rgba(15, 23, 42, 0.08)",
                padding: narrow ? 16 : 22,
                minHeight: 200
              }}
            >
              {tab === "overview" ? <OverviewPanel session={session} /> : null}
              {tab === "rubric" ? (
                <MdPanel html={session.rubric_md ? renderMarkdown(session.rubric_md) : null} />
              ) : null}
              {tab === "questions" ? (
                <MdPanel html={session.questions_md ? renderMarkdown(session.questions_md) : null} />
              ) : null}
              {tab === "exercises" ? (
                <MdPanel html={session.exercises_md ? renderMarkdown(session.exercises_md) : null} />
              ) : null}
              {tab === "resources" ? (
                <MdPanel html={session.resources_md ? renderMarkdown(session.resources_md) : null} />
              ) : null}
              {tab === "tasks" ? <TasksPanel packs={session.task_packs} /> : null}
            </section>

            {overviewError ? (
              <p style={{ marginTop: 12, fontSize: 13, color: "#b45309" }}>{overviewError}</p>
            ) : null}

            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                flexWrap: "wrap",
                gap: 12,
                marginTop: 28
              }}
            >
              {prevNum != null ? (
                <Link
                  href={`/course/${prevNum}` as Route}
                  style={{
                    padding: "10px 18px",
                    borderRadius: 8,
                    border: `1px solid ${GRAY_200}`,
                    background: "#fff",
                    color: "#334155",
                    fontWeight: 600,
                    textDecoration: "none",
                    fontSize: 14
                  }}
                >
                  ← Previous session
                </Link>
              ) : (
                <span />
              )}
              {nextNum != null ? (
                <Link
                  href={`/course/${nextNum}` as Route}
                  style={{
                    padding: "10px 18px",
                    borderRadius: 8,
                    background: INDIGO,
                    color: "#fff",
                    fontWeight: 600,
                    textDecoration: "none",
                    fontSize: 14,
                    boxShadow: "0 2px 8px rgba(99, 102, 241, 0.35)"
                  }}
                >
                  Next session →
                </Link>
              ) : null}
            </div>
          </>
        ) : null}
      </div>
    </AppShell>
  );
}

function OverviewPanel({ session }: { session: CourseSessionRead }) {
  return (
    <div>
      <div
        dangerouslySetInnerHTML={{
          __html: session.overview_md ? renderMarkdown(session.overview_md) : "<p>No overview.</p>"
        }}
      />
      {session.ai_tasks_md ? (
        <div style={{ marginTop: 28, paddingTop: 20, borderTop: `1px solid ${GRAY_200}` }}>
          <h3 style={{ margin: "0 0 12px", fontSize: 16, color: "#0f172a" }}>AI task notes</h3>
          <div dangerouslySetInnerHTML={{ __html: renderMarkdown(session.ai_tasks_md) }} />
        </div>
      ) : null}
      {session.objectives_json?.length ? (
        <div style={{ marginTop: 28 }}>
          <h3 style={{ margin: "0 0 12px", fontSize: 16, color: "#0f172a" }}>Objectives</h3>
          <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 10 }}>
            {session.objectives_json.map((obj) => (
              <li
                key={obj}
                style={{
                  display: "flex",
                  gap: 12,
                  alignItems: "flex-start",
                  fontSize: 15,
                  color: "#334155"
                }}
              >
                <span
                  style={{
                    width: 22,
                    height: 22,
                    borderRadius: 6,
                    background: "#d1fae5",
                    color: EMERALD,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 12,
                    flexShrink: 0,
                    fontWeight: 700
                  }}
                  aria-hidden
                >
                  ✓
                </span>
                <span>{obj}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {session.outline_json?.length ? (
        <div style={{ marginTop: 28 }}>
          <h3 style={{ margin: "0 0 14px", fontSize: 16, color: "#0f172a" }}>Outline</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
            {session.outline_json.map((section, i) => (
              <div
                key={`${section.title}-${i}`}
                style={{
                  borderLeft: `3px solid ${INDIGO}`,
                  paddingLeft: 14,
                  marginLeft: 2
                }}
              >
                <h4 style={{ margin: "0 0 8px", fontSize: 15, fontWeight: 700, color: "#0f172a" }}>
                  {section.title}
                </h4>
                <ul style={{ margin: 0, paddingLeft: 18, color: "#475569", fontSize: 14, lineHeight: 1.6 }}>
                  {(section.items ?? []).map((item) => (
                    <li key={item} style={{ marginBottom: 4 }}>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function MdPanel({ html }: { html: string | null }) {
  if (!html) {
    return <p style={{ margin: 0, color: "#64748b" }}>Nothing here yet.</p>;
  }
  return <div dangerouslySetInnerHTML={{ __html: html }} />;
}

function TasksPanel({ packs }: { packs: TaskPackSummary[] }) {
  if (!packs?.length) {
    return <p style={{ margin: 0, color: "#64748b" }}>No task packs linked to this session.</p>;
  }
  return (
    <div style={{ display: "grid", gap: 14 }}>
      {packs.map((p) => (
        <div
          key={p.id}
          style={{
            border: `1px solid ${GRAY_200}`,
            borderRadius: 8,
            padding: 16,
            display: "flex",
            flexDirection: "column",
            gap: 8,
            background: "#f9fafb"
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
            <div>
              <strong style={{ fontSize: 16, color: "#0f172a" }}>{p.name}</strong>
              <p style={{ margin: "6px 0 0", fontSize: 13, color: "#64748b" }}>
                {p.slug} · {p.language} · {p.task_count} tasks
              </p>
            </div>
            <Link
              href="/dashboard"
              style={{
                alignSelf: "flex-start",
                padding: "8px 16px",
                borderRadius: 8,
                background: INDIGO,
                color: "#fff",
                fontWeight: 600,
                fontSize: 14,
                textDecoration: "none",
                whiteSpace: "nowrap"
              }}
            >
              Start annotating
            </Link>
          </div>
          {p.description ? <p style={{ margin: 0, fontSize: 14, color: "#475569" }}>{p.description}</p> : null}
        </div>
      ))}
    </div>
  );
}
