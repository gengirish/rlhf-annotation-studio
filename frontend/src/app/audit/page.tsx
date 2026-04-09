"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { AppShell } from "@/components/AppShell";
import { Badge, Button, Card, EmptyState, Pagination, StatCard, Table, type Column } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { auditApi } from "@/lib/api-extensions";
import { useAppStore, useHasHydrated } from "@/lib/state/store";
import type { AuditLogEntry, AuditLogPage, AuditLogStats } from "@/types/extensions";

const PAGE_SIZE = 25;

function sumCounts(d: Record<string, number> | undefined): number {
  if (!d) return 0;
  return Object.values(d).reduce((a, b) => a + (typeof b === "number" ? b : 0), 0);
}

function parsePage(raw: unknown): AuditLogPage {
  if (!raw || typeof raw !== "object") {
    return { items: [], total: 0, skip: 0, limit: PAGE_SIZE };
  }
  const o = raw as Record<string, unknown>;
  return {
    items: Array.isArray(o.items) ? (o.items as AuditLogEntry[]) : [],
    total: Number(o.total ?? 0),
    skip: Number(o.skip ?? 0),
    limit: Number(o.limit ?? PAGE_SIZE)
  };
}

function parseStats(raw: unknown): AuditLogStats | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  return {
    last_24h: (o.last_24h as Record<string, number>) || {},
    last_7d: (o.last_7d as Record<string, number>) || {},
    last_30d: (o.last_30d as Record<string, number>) || {}
  };
}

type SortKey = "created_at" | "actor_id" | "action" | "resource_type" | "ip_address";

export default function AuditPage() {
  const router = useRouter();
  const user = useAppStore((s) => s.user);
  const sessionId = useAppStore((s) => s.sessionId);
  const hydrated = useHasHydrated();

  const [narrow, setNarrow] = useState(false);
  const [forbidden, setForbidden] = useState(false);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<AuditLogStats | null>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [items, setItems] = useState<AuditLogEntry[]>([]);

  const [filterAction, setFilterAction] = useState("");
  const [filterActor, setFilterActor] = useState("");
  const [filterResourceType, setFilterResourceType] = useState("");
  const [filterStart, setFilterStart] = useState("");
  const [filterEnd, setFilterEnd] = useState("");

  const [sortKey, setSortKey] = useState<SortKey>("created_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [filterEpoch, setFilterEpoch] = useState(0);

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 900px)");
    setNarrow(mq.matches);
    const fn = () => setNarrow(mq.matches);
    mq.addEventListener("change", fn);
    return () => mq.removeEventListener("change", fn);
  }, []);

  useEffect(() => {
    if (hydrated && (!user || !sessionId)) router.push("/auth");
  }, [hydrated, user, sessionId, router]);

  const fetchStats = useCallback(async () => {
    try {
      const raw = await auditApi.stats();
      setStats(parseStats(raw));
      setForbidden(false);
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) setForbidden(true);
    }
  }, []);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const skip = (page - 1) * PAGE_SIZE;
      const params: Record<string, string | number | undefined> = {
        skip,
        limit: PAGE_SIZE
      };
      if (filterAction.trim()) params.action = filterAction.trim();
      if (filterActor.trim()) params.actor_id = filterActor.trim();
      if (filterResourceType.trim()) params.resource_type = filterResourceType.trim();
      if (filterStart) params.start_date = new Date(filterStart).toISOString();
      if (filterEnd) params.end_date = new Date(filterEnd).toISOString();

      const raw = await auditApi.listLogs(params);
      const p = parsePage(raw);
      setItems(p.items);
      setTotal(p.total);
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) {
        setForbidden(true);
        setItems([]);
        setTotal(0);
      } else {
        toast.error(e instanceof Error ? e.message : "Failed to load audit log");
      }
    } finally {
      setLoading(false);
    }
  }, [page, filterAction, filterActor, filterResourceType, filterStart, filterEnd]);

  useEffect(() => {
    if (!sessionId) return;
    void fetchStats();
  }, [sessionId, fetchStats]);

  useEffect(() => {
    if (!sessionId || forbidden) return;
    void fetchLogs();
  }, [sessionId, forbidden, fetchLogs, filterEpoch]);

  const sortedItems = useMemo(() => {
    const copy = [...items];
    copy.sort((a, b) => {
      const av = (a as unknown as Record<string, unknown>)[sortKey];
      const bv = (b as unknown as Record<string, unknown>)[sortKey];
      const as = av === null || av === undefined ? "" : String(av);
      const bs = bv === null || bv === undefined ? "" : String(bv);
      const cmp = as.localeCompare(bs);
      return sortDir === "asc" ? cmp : -cmp;
    });
    return copy;
  }, [items, sortKey, sortDir]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const columns: Column<AuditLogEntry>[] = useMemo(
    () => [
      {
        key: "created_at",
        header: "Timestamp",
        render: (v) => new Date(String(v)).toLocaleString()
      },
      {
        key: "actor_id",
        header: "Actor",
        render: (v) => {
          const s = v ? String(v) : "—";
          return s.length > 14 ? `${s.slice(0, 10)}…` : s;
        }
      },
      { key: "action", header: "Action" },
      { key: "resource_type", header: "Resource" },
      {
        key: "resource_id",
        header: "Resource ID",
        render: (v) => (v ? String(v).slice(0, 28) : "—")
      },
      {
        key: "details_json",
        header: "Details",
        render: (v) => {
          if (!v || typeof v !== "object") return "—";
          const keys = Object.keys(v as object).length;
          return keys ? `${keys} field(s)` : "—";
        }
      },
      { key: "ip_address", header: "IP", render: (v) => (v ? String(v) : "—") }
    ],
    []
  );

  function applyFilters() {
    setPage(1);
    setFilterEpoch((e) => e + 1);
  }

  const expanded = expandedId ? sortedItems.find((x) => x.id === expandedId) : null;

  if (!hydrated) return null;
  if (!user || !sessionId) return null;

  if (forbidden) {
    return (
      <AppShell>
        <header className="card" style={{ padding: 16 }}>
          <h1 style={{ margin: 0 }}>Audit log</h1>
          <p style={{ margin: "8px 0 0", color: "var(--muted)" }}>
            Admin access is required to view organization audit history.
          </p>
        </header>
      </AppShell>
    );
  }

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
          <h1 style={{ margin: 0 }}>Audit log</h1>
          <p style={{ margin: "6px 0 0", color: "var(--muted)" }}>Immutable record of sensitive actions</p>
        </div>
      </header>

      <section
        style={{
          marginTop: 18,
          display: "grid",
          gridTemplateColumns: narrow ? "1fr" : "repeat(3, minmax(0, 1fr))",
          gap: 12
        }}
      >
        <StatCard
          label="Actions (24h)"
          value={stats ? sumCounts(stats.last_24h) : loading ? "…" : "0"}
          icon="⏱"
        />
        <StatCard label="Actions (7d)" value={stats ? sumCounts(stats.last_7d) : loading ? "…" : "0"} icon="▦" />
        <StatCard
          label="Actions (30d)"
          value={stats ? sumCounts(stats.last_30d) : loading ? "…" : "0"}
          icon="▣"
        />
      </section>

      <div style={{ marginTop: 18 }}>
        <Card title="Filters" subtitle="Query audit entries; results are paginated server-side">
          <div
            style={{
              display: "grid",
              gridTemplateColumns: narrow ? "1fr" : "repeat(2, minmax(0, 1fr))",
              gap: 12
            }}
          >
            <label style={{ display: "grid", gap: 6 }}>
              <span style={{ fontSize: 13, color: "#64748b" }}>Action</span>
              <input
                className="input"
                value={filterAction}
                onChange={(e) => setFilterAction(e.target.value)}
                placeholder="e.g. org.update"
              />
            </label>
            <label style={{ display: "grid", gap: 6 }}>
              <span style={{ fontSize: 13, color: "#64748b" }}>Actor (UUID)</span>
              <input
                className="input"
                value={filterActor}
                onChange={(e) => setFilterActor(e.target.value)}
                placeholder="Annotator id"
              />
            </label>
            <label style={{ display: "grid", gap: 6 }}>
              <span style={{ fontSize: 13, color: "#64748b" }}>Resource type</span>
              <input
                className="input"
                value={filterResourceType}
                onChange={(e) => setFilterResourceType(e.target.value)}
                placeholder="e.g. task_pack"
              />
            </label>
            <label style={{ display: "grid", gap: 6 }}>
              <span style={{ fontSize: 13, color: "#64748b" }}>Start</span>
              <input
                className="input"
                type="datetime-local"
                value={filterStart}
                onChange={(e) => setFilterStart(e.target.value)}
              />
            </label>
            <label style={{ display: "grid", gap: 6 }}>
              <span style={{ fontSize: 13, color: "#64748b" }}>End</span>
              <input
                className="input"
                type="datetime-local"
                value={filterEnd}
                onChange={(e) => setFilterEnd(e.target.value)}
              />
            </label>
          </div>
          <div
            style={{
              marginTop: 14,
              display: "flex",
              flexWrap: "wrap",
              gap: 10,
              alignItems: "center"
            }}
          >
            <Button variant="primary" onClick={applyFilters}>
              Apply filters
            </Button>
            <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
              Sort by
              <select
                className="input"
                style={{ width: 160 }}
                value={sortKey}
                onChange={(e) => setSortKey(e.target.value as SortKey)}
              >
                <option value="created_at">Timestamp</option>
                <option value="actor_id">Actor</option>
                <option value="action">Action</option>
                <option value="resource_type">Resource</option>
                <option value="ip_address">IP</option>
              </select>
            </label>
            <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
              Direction
              <select
                className="input"
                style={{ width: 120 }}
                value={sortDir}
                onChange={(e) => setSortDir(e.target.value as "asc" | "desc")}
              >
                <option value="desc">Descending</option>
                <option value="asc">Ascending</option>
              </select>
            </label>
            <Badge variant="info">{total} total</Badge>
          </div>
        </Card>
      </div>

      <div style={{ marginTop: 18 }}>
        <Card title="Events" subtitle="Click a row to expand JSON details">
          {!loading && sortedItems.length === 0 ? (
            <EmptyState title="No audit entries" description="Try adjusting filters or time range." />
          ) : (
            <>
              <Table
                columns={columns}
                data={sortedItems}
                loading={loading}
                emptyMessage="No rows"
                onRowClick={(row) => setExpandedId((id) => (id === row.id ? null : row.id))}
              />
              <Pagination currentPage={page} totalPages={totalPages} onPageChange={setPage} />
            </>
          )}
        </Card>
      </div>

      {expanded ? (
        <div style={{ marginTop: 18 }}>
          <Card
            title="Entry details"
            subtitle={expanded.id}
            headerAction={
              <Button variant="ghost" size="sm" onClick={() => setExpandedId(null)}>
                Close
              </Button>
            }
          >
            <pre
              style={{
                margin: 0,
                padding: 14,
                background: "#0f172a",
                color: "#e2e8f0",
                borderRadius: 8,
                fontSize: 12,
                overflow: "auto",
                maxHeight: 360
              }}
            >
              {JSON.stringify(expanded.details_json ?? {}, null, 2)}
            </pre>
          </Card>
        </div>
      ) : null}
    </AppShell>
  );
}
