"use client";

import type { CSSProperties } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { AppShell } from "@/components/AppShell";
import { ApiError, api, type Organization, type OrgMember } from "@/lib/api";
import { useAppStore } from "@/lib/state/store";

const ORG_ID_STORAGE_KEY = "rlhf_active_org_id";

function planBadgeStyle(tier: string): CSSProperties {
  const t = tier.toLowerCase();
  if (t === "free") return { background: "#6b7280", color: "#fff" };
  if (t === "pro") return { background: "#6366f1", color: "#fff" };
  if (t === "enterprise") return { background: "#f59e0b", color: "#0f172a" };
  return { background: "#6b7280", color: "#fff" };
}

function ProgressBar({ used, max, label }: { used: number; max: number; label: string }) {
  const pct = max > 0 ? Math.min(100, Math.round((used / max) * 100)) : 0;
  return (
    <div style={{ marginTop: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, color: "var(--muted)" }}>
        <span>{label}</span>
        <span>
          {used} / {max}
        </span>
      </div>
      <div
        style={{
          marginTop: 6,
          height: 10,
          borderRadius: 999,
          background: "var(--border)",
          overflow: "hidden"
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${pct}%`,
            background: "var(--primary)",
            borderRadius: 999,
            transition: "width 0.2s ease"
          }}
        />
      </div>
    </div>
  );
}

export default function SettingsPage() {
  const router = useRouter();
  const user = useAppStore((s) => s.user);
  const sessionId = useAppStore((s) => s.sessionId);

  const [orgId, setOrgId] = useState<string | null>(null);
  const [org, setOrg] = useState<Organization | null>(null);
  const [members, setMembers] = useState<OrgMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [createName, setCreateName] = useState("");
  const [createSlug, setCreateSlug] = useState("");
  const [createSlugTouched, setCreateSlugTouched] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [savingOrg, setSavingOrg] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);

  useEffect(() => {
    if (!user || !sessionId) {
      router.push("/auth");
    }
  }, [user, sessionId, router]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = localStorage.getItem(ORG_ID_STORAGE_KEY);
    setOrgId(stored);
  }, []);

  const loadOrg = useCallback(async (id: string) => {
    setLoading(true);
    setLoadFailed(false);
    try {
      const [o, m] = await Promise.all([api.getOrg(id), api.getOrgMembers(id)]);
      setOrg(o);
      setMembers(m);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        localStorage.removeItem(ORG_ID_STORAGE_KEY);
        setOrgId(null);
        setOrg(null);
        setMembers([]);
        toast.message("No organization found. Create one below.");
      } else {
        setLoadFailed(true);
        setOrg(null);
        setMembers([]);
        toast.error(err instanceof Error ? err.message : "Failed to load organization");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!orgId) {
      setLoading(false);
      setOrg(null);
      setMembers([]);
      return;
    }
    void loadOrg(orgId);
  }, [orgId, loadOrg]);

  function slugify(name: string): string {
    return (
      name
        .toLowerCase()
        .trim()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, "") || "org"
    );
  }

  useEffect(() => {
    if (createSlugTouched) return;
    setCreateSlug(slugify(createName));
  }, [createName, createSlugTouched]);

  async function handleCreateOrg(e: React.FormEvent) {
    e.preventDefault();
    const name = createName.trim();
    const slug = createSlug.trim();
    if (!name || !slug) {
      toast.error("Name and slug are required");
      return;
    }
    setSavingOrg(true);
    try {
      const created = await api.createOrg({ name, slug });
      localStorage.setItem(ORG_ID_STORAGE_KEY, created.id);
      setOrgId(created.id);
      setOrg(created);
      setMembers([]);
      setCreateName("");
      setCreateSlug("");
      setCreateSlugTouched(false);
      toast.success("Organization created");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Create failed");
    } finally {
      setSavingOrg(false);
    }
  }

  async function handleAddMember(e: React.FormEvent) {
    e.preventDefault();
    if (!orgId) return;
    const email = inviteEmail.trim();
    if (!email) {
      toast.error("Email is required");
      return;
    }
    try {
      await api.addOrgMember(orgId, email);
      setInviteEmail("");
      toast.success("Invitation sent");
      await loadOrg(orgId);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to add member");
    }
  }

  const usedSeats = useMemo(() => {
    if (org?.used_seats != null) return org.used_seats;
    return members.length;
  }, [org?.used_seats, members.length]);

  const usedPacks = org?.used_packs ?? 0;

  if (!user || !sessionId) {
    return null;
  }

  return (
    <AppShell>
      <header className="card" style={{ padding: 16, marginBottom: 18 }}>
        <h1 style={{ margin: 0 }}>Settings</h1>
      </header>

      {loading ? (
        <p style={{ color: "var(--muted)" }}>Loading…</p>
      ) : orgId && loadFailed ? (
        <section className="card" style={{ padding: 20 }}>
          <h2 style={{ marginTop: 0 }}>Could not load organization</h2>
          <p style={{ color: "var(--muted)" }}>Check your connection or permissions, then retry.</p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginTop: 12 }}>
            <button type="button" className="btn btn-primary" onClick={() => void loadOrg(orgId)}>
              Retry
            </button>
            <button
              type="button"
              className="btn"
              onClick={() => {
                localStorage.removeItem(ORG_ID_STORAGE_KEY);
                setOrgId(null);
                setOrg(null);
                setMembers([]);
                setLoadFailed(false);
              }}
            >
              Clear saved org
            </button>
          </div>
        </section>
      ) : !orgId || !org ? (
        <section className="card" style={{ padding: 20 }}>
          <h2 style={{ marginTop: 0 }}>Create Organization</h2>
          <p style={{ color: "var(--muted)", marginTop: 0 }}>
            You do not have an organization yet. Create one to manage team seats and task packs.
          </p>
          <form onSubmit={handleCreateOrg} style={{ maxWidth: 420, display: "grid", gap: 12 }}>
            <label style={{ display: "grid", gap: 6 }}>
              <span style={{ fontSize: 14 }}>Name</span>
              <input
                className="input"
                value={createName}
                onChange={(e) => setCreateName(e.target.value)}
                placeholder="Acme RLHF"
              />
            </label>
            <label style={{ display: "grid", gap: 6 }}>
              <span style={{ fontSize: 14 }}>Slug</span>
              <input
                className="input"
                value={createSlug}
                onChange={(e) => {
                  setCreateSlugTouched(true);
                  setCreateSlug(e.target.value);
                }}
                placeholder="acme-rlhf"
              />
            </label>
            <button type="submit" className="btn btn-primary" disabled={savingOrg}>
              {savingOrg ? "Creating…" : "Create Organization"}
            </button>
          </form>
        </section>
      ) : (
        <>
          <section className="card" style={{ padding: 20, marginBottom: 18 }}>
            <h2 style={{ marginTop: 0 }}>Organization</h2>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "center" }}>
              <div>
                <p style={{ margin: 0, fontSize: 22, fontWeight: 600 }}>{org.name}</p>
                <p style={{ margin: "6px 0 0", color: "var(--muted)" }}>/{org.slug}</p>
              </div>
              <span
                style={{
                  ...planBadgeStyle(org.plan_tier),
                  fontSize: 12,
                  fontWeight: 600,
                  padding: "4px 10px",
                  borderRadius: 999,
                  textTransform: "capitalize"
                }}
              >
                {org.plan_tier}
              </span>
            </div>
            <div style={{ marginTop: 16, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12 }}>
              <div>
                <p style={{ margin: 0, fontSize: 13, color: "var(--muted)" }}>Members</p>
                <p style={{ margin: "4px 0 0", fontSize: 20 }}>{members.length}</p>
              </div>
              <div>
                <p style={{ margin: 0, fontSize: 13, color: "var(--muted)" }}>Pack limit</p>
                <p style={{ margin: "4px 0 0", fontSize: 20 }}>{org.max_packs}</p>
              </div>
            </div>
          </section>

          <section className="card" style={{ padding: 20, marginBottom: 18 }}>
            <h2 style={{ marginTop: 0 }}>Plan &amp; usage</h2>
            <p style={{ margin: "0 0 8px", color: "var(--muted)" }}>
              Current plan:{" "}
              <span style={{ fontWeight: 600, textTransform: "capitalize" }}>{org.plan_tier}</span>
            </p>
            <ProgressBar used={usedSeats} max={Math.max(1, org.max_seats)} label="Seats" />
            <ProgressBar used={usedPacks} max={Math.max(1, org.max_packs)} label="Task packs" />
          </section>

          <section className="card" style={{ padding: 20 }}>
            <h2 style={{ marginTop: 0 }}>Team members</h2>
            <ul style={{ listStyle: "none", padding: 0, margin: "0 0 16px" }}>
              {members.length === 0 ? (
                <li style={{ color: "var(--muted)" }}>No members yet.</li>
              ) : (
                members.map((m) => (
                  <li
                    key={m.id}
                    className="card"
                    style={{ padding: 12, marginBottom: 8, border: "1px solid var(--border)" }}
                  >
                    <p style={{ margin: 0, fontWeight: 600 }}>{m.name}</p>
                    <p style={{ margin: "4px 0 0", fontSize: 14, color: "var(--muted)" }}>{m.email}</p>
                  </li>
                ))
              )}
            </ul>
            <form onSubmit={handleAddMember} style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "flex-end" }}>
              <label style={{ flex: "1 1 220px", display: "grid", gap: 6 }}>
                <span style={{ fontSize: 14 }}>Email</span>
                <input
                  className="input"
                  type="email"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="teammate@example.com"
                />
              </label>
              <button type="submit" className="btn btn-primary">
                Add member
              </button>
            </form>
          </section>
        </>
      )}
    </AppShell>
  );
}
