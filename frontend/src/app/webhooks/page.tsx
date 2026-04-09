"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { AppShell } from "@/components/AppShell";
import { Badge, Button, Card, EmptyState, Modal } from "@/components/ui";
import { webhookApi } from "@/lib/api-extensions";
import { useAppStore } from "@/lib/state/store";
import type { WebhookDelivery, WebhookEndpoint } from "@/types/extensions";

const WEBHOOK_EVENTS = [
  "annotation.submitted",
  "annotation.updated",
  "review.assigned",
  "review.submitted",
  "review.approved",
  "review.rejected",
  "dataset.created",
  "dataset.exported",
  "task_pack.created",
  "test.ping"
] as const;

function parseEndpoints(raw: unknown): WebhookEndpoint[] {
  return Array.isArray(raw) ? (raw as WebhookEndpoint[]) : [];
}

function parseDeliveries(raw: unknown): WebhookDelivery[] {
  return Array.isArray(raw) ? (raw as WebhookDelivery[]) : [];
}

export default function WebhooksPage() {
  const router = useRouter();
  const user = useAppStore((s) => s.user);
  const sessionId = useAppStore((s) => s.sessionId);

  const [narrow, setNarrow] = useState(false);
  const [loading, setLoading] = useState(true);
  const [endpoints, setEndpoints] = useState<WebhookEndpoint[]>([]);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [deliveriesById, setDeliveriesById] = useState<Record<string, WebhookDelivery[]>>({});
  const [deliveriesLoading, setDeliveriesLoading] = useState<string | null>(null);
  const [testingId, setTestingId] = useState<string | null>(null);

  const [modalOpen, setModalOpen] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [formUrl, setFormUrl] = useState("");
  const [formEvents, setFormEvents] = useState<Set<string>>(new Set(["test.ping"]));
  const [formActive, setFormActive] = useState(true);
  const [saving, setSaving] = useState(false);

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

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const raw = await webhookApi.list();
      setEndpoints(parseEndpoints(raw));
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to load webhooks");
      setEndpoints([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (sessionId) void load();
  }, [sessionId, load]);

  async function loadDeliveries(id: string) {
    if (deliveriesById[id]) return;
    setDeliveriesLoading(id);
    try {
      const raw = await webhookApi.deliveries(id, { limit: 30 });
      setDeliveriesById((prev) => ({ ...prev, [id]: parseDeliveries(raw) }));
    } catch {
      setDeliveriesById((prev) => ({ ...prev, [id]: [] }));
    } finally {
      setDeliveriesLoading(null);
    }
  }

  function toggleExpand(id: string) {
    if (expandedId === id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(id);
    void loadDeliveries(id);
  }

  function openCreate() {
    setEditId(null);
    setFormUrl("");
    setFormEvents(new Set(["test.ping"]));
    setFormActive(true);
    setModalOpen(true);
  }

  function openEdit(ep: WebhookEndpoint) {
    setEditId(ep.id);
    setFormUrl(ep.url);
    setFormEvents(new Set(ep.events));
    setFormActive(ep.is_active);
    setModalOpen(true);
  }

  function toggleEvent(ev: string) {
    setFormEvents((prev) => {
      const next = new Set(prev);
      if (next.has(ev)) next.delete(ev);
      else next.add(ev);
      return next;
    });
  }

  async function saveWebhook() {
    if (!formUrl.trim()) {
      toast.error("URL is required");
      return;
    }
    if (formEvents.size === 0) {
      toast.error("Select at least one event");
      return;
    }
    setSaving(true);
    try {
      if (editId) {
        await webhookApi.update(editId, {
          url: formUrl.trim(),
          events: Array.from(formEvents),
          is_active: formActive
        });
        toast.success("Webhook updated");
      } else {
        await webhookApi.create({
          url: formUrl.trim(),
          events: Array.from(formEvents),
          is_active: formActive
        });
        toast.success("Webhook created");
      }
      setModalOpen(false);
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function handleTest(id: string) {
    setTestingId(id);
    try {
      const raw = await webhookApi.test(id, { event: "test.ping" });
      const d = raw as WebhookDelivery;
      toast.success(
        d?.success ? `Ping OK (${d.response_status ?? "?"})` : "Delivery recorded (check success flag)"
      );
      setDeliveriesById((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
      if (expandedId === id) void loadDeliveries(id);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Test failed");
    } finally {
      setTestingId(null);
    }
  }

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
          flexWrap: "wrap",
          gap: 12
        }}
      >
        <div>
          <h1 style={{ margin: 0 }}>Webhooks</h1>
          <p style={{ margin: "6px 0 0", color: "var(--muted)" }}>Event deliveries and observability</p>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <Button variant="primary" onClick={openCreate}>
            Add webhook
          </Button>
        </div>
      </header>

      {loading ? (
        <p style={{ marginTop: 18, color: "#64748b" }}>Loading…</p>
      ) : endpoints.length === 0 ? (
        <div style={{ marginTop: 18 }}>
          <EmptyState
            title="No webhooks"
            description="Register HTTPS endpoints to receive annotation, review, and dataset events."
            action={{ label: "Add webhook", onClick: openCreate }}
          />
        </div>
      ) : (
        <div style={{ marginTop: 18, display: "grid", gap: 12 }}>
          {endpoints.map((ep) => {
            const expanded = expandedId === ep.id;
            const deliveries = deliveriesById[ep.id];
            const dLoading = deliveriesLoading === ep.id;
            return (
              <Card key={ep.id} padding="0">
                <div
                  style={{
                    padding: 16,
                    display: "flex",
                    flexDirection: narrow ? "column" : "row",
                    gap: 12,
                    justifyContent: "space-between",
                    alignItems: narrow ? "stretch" : "center"
                  }}
                >
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <code
                      style={{
                        display: "block",
                        fontSize: 13,
                        wordBreak: "break-all",
                        background: "#f1f5f9",
                        padding: "8px 10px",
                        borderRadius: 8
                      }}
                    >
                      {ep.url}
                    </code>
                    <div style={{ marginTop: 10, display: "flex", flexWrap: "wrap", gap: 6 }}>
                      {ep.events.slice(0, 6).map((ev) => (
                        <Badge key={ev} variant="info">
                          {ev}
                        </Badge>
                      ))}
                      {ep.events.length > 6 ? (
                        <Badge variant="default">+{ep.events.length - 6}</Badge>
                      ) : null}
                    </div>
                    <p style={{ margin: "10px 0 0", fontSize: 12, color: "#64748b" }}>
                      Failures: {ep.failure_count} · Last:{" "}
                      {ep.last_triggered_at ? new Date(ep.last_triggered_at).toLocaleString() : "—"}
                    </p>
                  </div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
                    <Badge variant={ep.is_active ? "success" : "default"}>
                      {ep.is_active ? "active" : "inactive"}
                    </Badge>
                    <Button size="sm" variant="secondary" onClick={() => openEdit(ep)}>
                      Edit
                    </Button>
                    <Button
                      size="sm"
                      variant="primary"
                      loading={testingId === ep.id}
                      onClick={() => void handleTest(ep.id)}
                    >
                      Test ping
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => toggleExpand(ep.id)}>
                      {expanded ? "Hide deliveries" : "Deliveries"}
                    </Button>
                  </div>
                </div>
                {expanded ? (
                  <div style={{ padding: "0 16px 16px", borderTop: "1px solid #e5e7eb" }}>
                    <h3 style={{ fontSize: 14, margin: "12px 0 8px" }}>Recent deliveries</h3>
                    {dLoading ? (
                      <p style={{ color: "#64748b" }}>Loading…</p>
                    ) : !deliveries?.length ? (
                      <p style={{ color: "#94a3b8" }}>No deliveries yet.</p>
                    ) : (
                      <div style={{ overflowX: "auto" }}>
                        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                          <thead>
                            <tr>
                              <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e5e7eb" }}>
                                Time
                              </th>
                              <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e5e7eb" }}>
                                Event
                              </th>
                              <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e5e7eb" }}>
                                Status
                              </th>
                              <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e5e7eb" }}>
                                ms
                              </th>
                              <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e5e7eb" }}>
                                OK
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            {deliveries.map((d) => (
                              <tr key={d.id}>
                                <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9", whiteSpace: "nowrap" }}>
                                  {new Date(d.created_at).toLocaleString()}
                                </td>
                                <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>{d.event}</td>
                                <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>
                                  {d.response_status ?? "—"}
                                </td>
                                <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>
                                  {d.duration_ms ?? "—"}
                                </td>
                                <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>
                                  <Badge variant={d.success ? "success" : "danger"}>
                                    {d.success ? "yes" : "no"}
                                  </Badge>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                ) : null}
              </Card>
            );
          })}
        </div>
      )}

      <Modal
        isOpen={modalOpen}
        onClose={() => !saving && setModalOpen(false)}
        title={editId ? "Edit webhook" : "Add webhook"}
        footer={
          <>
            <Button variant="secondary" disabled={saving} onClick={() => setModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" loading={saving} onClick={() => void saveWebhook()}>
              {editId ? "Save" : "Create"}
            </Button>
          </>
        }
      >
        <label style={{ display: "grid", gap: 6, marginBottom: 12 }}>
          <span style={{ fontSize: 13, color: "#64748b" }}>URL</span>
          <input
            className="input"
            value={formUrl}
            onChange={(e) => setFormUrl(e.target.value)}
            placeholder="https://example.com/hooks/rlhf"
          />
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14, fontSize: 14 }}>
          <input type="checkbox" checked={formActive} onChange={(e) => setFormActive(e.target.checked)} />
          Active
        </label>
        <span style={{ fontSize: 13, color: "#64748b", display: "block", marginBottom: 8 }}>Events</span>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: narrow ? "1fr" : "1fr 1fr",
            gap: 8,
            maxHeight: 220,
            overflowY: "auto",
            padding: 8,
            border: "1px solid #e5e7eb",
            borderRadius: 8
          }}
        >
          {WEBHOOK_EVENTS.map((ev) => (
            <label key={ev} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
              <input type="checkbox" checked={formEvents.has(ev)} onChange={() => toggleEvent(ev)} />
              {ev}
            </label>
          ))}
        </div>
      </Modal>
    </AppShell>
  );
}
