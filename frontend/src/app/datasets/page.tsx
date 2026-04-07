"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { Badge, Button, Card, EmptyState, Modal } from "@/components/ui";
import { api, type TaskPackSummary } from "@/lib/api";
import { datasetApi } from "@/lib/api-extensions";
import { useAppStore } from "@/lib/state/store";
import type { Dataset, DatasetDetail, DatasetVersion, ExportPayload } from "@/types/extensions";

function parseList(raw: unknown): { items: Dataset[]; total: number } {
  if (!raw || typeof raw !== "object") return { items: [], total: 0 };
  const o = raw as { items?: unknown; total?: unknown };
  const items = Array.isArray(o.items) ? (o.items as Dataset[]) : [];
  const total = Number(o.total ?? items.length);
  return { items, total };
}

function parseDetail(raw: unknown): DatasetDetail | null {
  if (!raw || typeof raw !== "object") return null;
  const d = raw as DatasetDetail;
  if (!d.id || !d.name) return null;
  return { ...d, versions: Array.isArray(d.versions) ? d.versions : [] };
}

function downloadExport(payload: ExportPayload) {
  const mime =
    payload.format === "csv"
      ? "text/csv"
      : payload.format === "jsonl" || payload.format === "dpo" || payload.format === "orpo"
        ? "application/json"
        : "text/plain";
  const blob = new Blob([payload.data], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = payload.filename || `export.${payload.format}`;
  a.click();
  URL.revokeObjectURL(url);
}

const TASK_TYPES = ["comparison", "rating", "ranking", "mixed"] as const;

export default function DatasetsPage() {
  const router = useRouter();
  const user = useAppStore((s) => s.user);
  const sessionId = useAppStore((s) => s.sessionId);

  const [narrow, setNarrow] = useState(false);
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState<Dataset[]>([]);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [detailById, setDetailById] = useState<Record<string, DatasetDetail>>({});
  const [detailLoading, setDetailLoading] = useState<string | null>(null);
  const [packs, setPacks] = useState<TaskPackSummary[]>([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [formName, setFormName] = useState("");
  const [formDesc, setFormDesc] = useState("");
  const [formType, setFormType] = useState<string>("mixed");
  const [selectedPackIds, setSelectedPackIds] = useState<Set<string>>(new Set());
  const [exporting, setExporting] = useState<string | null>(null);
  const [diffV1, setDiffV1] = useState<number>(1);
  const [diffV2, setDiffV2] = useState<number>(2);
  const [diffResult, setDiffResult] = useState<unknown>(null);
  const [diffLoading, setDiffLoading] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 900px)");
    setNarrow(mq.matches);
    const fn = () => setNarrow(mq.matches);
    mq.addEventListener("change", fn);
    return () => mq.removeEventListener("change", fn);
  }, []);

  useEffect(() => {
    if (!user || !sessionId) router.push("/auth");
  }, [user, sessionId, router]);

  const loadList = useCallback(async () => {
    setLoading(true);
    try {
      const raw = await datasetApi.list({ limit: 100 });
      const { items: list } = parseList(raw);
      setItems(list);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to load datasets");
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!sessionId) return;
    void loadList();
  }, [sessionId, loadList]);

  useEffect(() => {
    if (!sessionId) return;
    void api
      .getAllTaskPacks()
      .then(setPacks)
      .catch(() => setPacks([]));
  }, [sessionId]);

  async function ensureDetail(id: string) {
    if (detailById[id]) return;
    setDetailLoading(id);
    try {
      const raw = await datasetApi.get(id);
      const d = parseDetail(raw);
      if (d) setDetailById((prev) => ({ ...prev, [id]: d }));
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to load dataset");
    } finally {
      setDetailLoading(null);
    }
  }

  function toggleExpand(id: string) {
    if (expandedId === id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(id);
    void ensureDetail(id);
  }

  async function handleExport(datasetId: string, version: number, format: string) {
    const key = `${datasetId}-${version}-${format}`;
    setExporting(key);
    try {
      const raw = await datasetApi.exportVersion(datasetId, version, format);
      const p = raw as ExportPayload;
      if (p?.data && p?.filename) {
        downloadExport(p);
        toast.success(`Exported ${p.task_count} tasks`);
      } else {
        toast.error("Unexpected export response");
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Export failed");
    } finally {
      setExporting(null);
    }
  }

  async function handleCreate() {
    if (!formName.trim()) {
      toast.error("Name is required");
      return;
    }
    setCreating(true);
    try {
      await datasetApi.create({
        name: formName.trim(),
        description: formDesc.trim() || null,
        task_type: formType,
        tags: [],
        source_pack_ids: Array.from(selectedPackIds)
      });
      toast.success("Dataset created");
      setCreateOpen(false);
      setFormName("");
      setFormDesc("");
      setSelectedPackIds(new Set());
      await loadList();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Create failed");
    } finally {
      setCreating(false);
    }
  }

  async function runDiff(datasetId: string) {
    setDiffLoading(true);
    setDiffResult(null);
    try {
      const raw = await datasetApi.diff(datasetId, diffV1, diffV2);
      setDiffResult(raw);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Diff failed");
    } finally {
      setDiffLoading(false);
    }
  }

  function togglePack(id: string) {
    setSelectedPackIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  if (!user || !sessionId) return null;

  return (
    <main className="container">
      <header
        className="card"
        style={{
          padding: 16,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 12
        }}
      >
        <div>
          <h1 style={{ margin: 0 }}>Datasets</h1>
          <p style={{ margin: "6px 0 0", color: "var(--muted)" }}>Versioned exports for training pipelines</p>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <Button variant="primary" onClick={() => setCreateOpen(true)}>
            Create dataset
          </Button>
          <Link href="/dashboard" className="btn">
            ← Dashboard
          </Link>
        </div>
      </header>

      {loading ? (
        <p style={{ marginTop: 18, color: "#64748b" }}>Loading datasets…</p>
      ) : items.length === 0 ? (
        <div style={{ marginTop: 18 }}>
          <EmptyState
            title="No datasets yet"
            description="Create a dataset from task packs and export JSONL, DPO, ORPO, or CSV for downstream training."
            action={{ label: "Create dataset", onClick: () => setCreateOpen(true) }}
          />
        </div>
      ) : (
        <div style={{ marginTop: 18, display: "grid", gap: 12 }}>
          {items.map((ds) => {
            const expanded = expandedId === ds.id;
            const detail = detailById[ds.id];
            const busy = detailLoading === ds.id;
            return (
              <Card key={ds.id} padding="0" style={{ overflow: "hidden" }}>
                <button
                  type="button"
                  onClick={() => toggleExpand(ds.id)}
                  style={{
                    width: "100%",
                    textAlign: "left",
                    padding: 16,
                    border: "none",
                    background: expanded ? "#f9fafb" : "#fff",
                    cursor: "pointer",
                    display: "flex",
                    flexDirection: narrow ? "column" : "row",
                    alignItems: narrow ? "flex-start" : "center",
                    justifyContent: "space-between",
                    gap: 12
                  }}
                >
                  <div style={{ minWidth: 0 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                      <strong style={{ fontSize: 16 }}>{ds.name}</strong>
                      <Badge variant="info">{ds.task_type}</Badge>
                    </div>
                    <p style={{ margin: "8px 0 0", fontSize: 13, color: "#64748b" }}>
                      {ds.description || "No description"}
                    </p>
                    <p style={{ margin: "8px 0 0", fontSize: 12, color: "#94a3b8" }}>
                      Versions: {ds.version_count} · Updated {new Date(ds.updated_at).toLocaleDateString()}
                    </p>
                  </div>
                  <span style={{ fontSize: 13, color: "#6366f1", fontWeight: 600 }}>{expanded ? "Hide" : "Expand"}</span>
                </button>
                {expanded ? (
                  <div style={{ padding: "0 16px 16px", borderTop: "1px solid #e5e7eb" }}>
                    {busy ? (
                      <p style={{ color: "#64748b" }}>Loading details…</p>
                    ) : detail ? (
                      <>
                        <h3 style={{ fontSize: 14, margin: "14px 0 8px" }}>Version history</h3>
                        <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
                          {detail.versions.map((v: DatasetVersion) => (
                            <li
                              key={v.id}
                              style={{
                                padding: 12,
                                border: "1px solid #e5e7eb",
                                borderRadius: 8,
                                marginBottom: 8,
                                background: "#fff"
                              }}
                            >
                              <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
                                <strong>v{v.version}</strong>
                                <span style={{ fontSize: 12, color: "#64748b" }}>
                                  {new Date(v.created_at).toLocaleString()}
                                </span>
                              </div>
                              <div style={{ marginTop: 10, display: "flex", flexWrap: "wrap", gap: 8 }}>
                                {(["jsonl", "dpo", "orpo", "csv"] as const).map((fmt) => (
                                  <Button
                                    key={fmt}
                                    size="sm"
                                    variant="secondary"
                                    loading={exporting === `${ds.id}-${v.version}-${fmt}`}
                                    onClick={() => void handleExport(ds.id, v.version, fmt)}
                                  >
                                    Export {fmt.toUpperCase()}
                                  </Button>
                                ))}
                              </div>
                            </li>
                          ))}
                        </ul>
                        <h3 style={{ fontSize: 14, margin: "18px 0 8px" }}>Version diff</h3>
                        <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center" }}>
                          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>
                            v1
                            <input
                              className="input"
                              type="number"
                              min={1}
                              value={diffV1}
                              onChange={(e) => setDiffV1(Number(e.target.value))}
                              style={{ width: 72 }}
                            />
                          </label>
                          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>
                            v2
                            <input
                              className="input"
                              type="number"
                              min={1}
                              value={diffV2}
                              onChange={(e) => setDiffV2(Number(e.target.value))}
                              style={{ width: 72 }}
                            />
                          </label>
                          <Button
                            variant="primary"
                            size="sm"
                            loading={diffLoading}
                            onClick={() => void runDiff(ds.id)}
                          >
                            Compare
                          </Button>
                        </div>
                        {diffResult !== null && expandedId === ds.id ? (
                          <pre
                            style={{
                              marginTop: 12,
                              padding: 12,
                              background: "#0f172a",
                              color: "#e2e8f0",
                              borderRadius: 8,
                              fontSize: 12,
                              overflow: "auto",
                              maxHeight: 280
                            }}
                          >
                            {JSON.stringify(diffResult, null, 2)}
                          </pre>
                        ) : null}
                      </>
                    ) : (
                      <p style={{ color: "#94a3b8" }}>Could not load dataset detail.</p>
                    )}
                  </div>
                ) : null}
              </Card>
            );
          })}
        </div>
      )}

      <Modal
        isOpen={createOpen}
        onClose={() => !creating && setCreateOpen(false)}
        title="Create dataset"
        size="lg"
        footer={
          <>
            <Button variant="secondary" disabled={creating} onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" loading={creating} onClick={() => void handleCreate()}>
              Create
            </Button>
          </>
        }
      >
        <div style={{ display: "grid", gap: 14 }}>
          <label style={{ display: "grid", gap: 6 }}>
            <span style={{ fontSize: 13, color: "#64748b" }}>Name</span>
            <input className="input" value={formName} onChange={(e) => setFormName(e.target.value)} />
          </label>
          <label style={{ display: "grid", gap: 6 }}>
            <span style={{ fontSize: 13, color: "#64748b" }}>Description</span>
            <textarea
              className="input"
              rows={3}
              value={formDesc}
              onChange={(e) => setFormDesc(e.target.value)}
            />
          </label>
          <label style={{ display: "grid", gap: 6 }}>
            <span style={{ fontSize: 13, color: "#64748b" }}>Task type</span>
            <select className="input" value={formType} onChange={(e) => setFormType(e.target.value)}>
              {TASK_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
          <div>
            <span style={{ fontSize: 13, color: "#64748b", display: "block", marginBottom: 8 }}>
              Source packs
            </span>
            <div
              style={{
                maxHeight: 200,
                overflowY: "auto",
                border: "1px solid #e5e7eb",
                borderRadius: 8,
                padding: 8
              }}
            >
              {packs.length === 0 ? (
                <p style={{ margin: 0, fontSize: 13, color: "#94a3b8" }}>No packs loaded</p>
              ) : (
                packs.map((p) => (
                  <label
                    key={p.slug}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      padding: "6px 0",
                      fontSize: 14,
                      cursor: "pointer"
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={selectedPackIds.has(p.id)}
                      onChange={() => togglePack(p.id)}
                    />
                    <span>
                      {p.name} <span style={{ color: "#94a3b8" }}>({p.task_count})</span>
                    </span>
                  </label>
                ))
              )}
            </div>
          </div>
        </div>
      </Modal>
    </main>
  );
}
