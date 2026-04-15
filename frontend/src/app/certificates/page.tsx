"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/api";
import type { CertificateRead, CertificateCreateBody, OrgMember } from "@/lib/api";
import { useAppStore, useHasHydrated } from "@/lib/state/store";

export default function CertificatesPage() {
  const router = useRouter();
  const { user, sessionId } = useAppStore();
  const hydrated = useHasHydrated();
  const [certs, setCerts] = useState<CertificateRead[]>([]);
  const [loading, setLoading] = useState(true);

  const [allCerts, setAllCerts] = useState<CertificateRead[]>([]);
  const [allLoading, setAllLoading] = useState(false);

  const [showIssue, setShowIssue] = useState(false);
  const [issueTitle, setIssueTitle] = useState("");
  const [issueDesc, setIssueDesc] = useState("");
  const [issueAnnotatorId, setIssueAnnotatorId] = useState("");
  const [issueType, setIssueType] = useState("course_completion");
  const [issuing, setIssuing] = useState(false);

  const [members, setMembers] = useState<OrgMember[]>([]);

  const isAdmin = user?.role === "admin";

  useEffect(() => {
    if (hydrated && (!user || !sessionId)) {
      router.push("/auth");
    }
  }, [hydrated, user, sessionId, router]);

  useEffect(() => {
    async function load() {
      try {
        setCerts(await api.getMyCertificates());
      } catch {
        toast.error("Failed to load certificates");
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, []);

  useEffect(() => {
    async function loadAll() {
      if (!isAdmin) return;
      setAllLoading(true);
      try {
        setAllCerts(await api.getAllCertificates());
      } catch {
        // silent
      } finally {
        setAllLoading(false);
      }
    }
    void loadAll();
  }, [isAdmin]);

  useEffect(() => {
    async function loadMembers() {
      if (!isAdmin || !user?.org_id) return;
      try {
        const m = await api.getOrgMembers(user.org_id);
        setMembers(m);
      } catch {
        // silent
      }
    }
    void loadMembers();
  }, [isAdmin, user?.org_id]);

  async function handleIssue() {
    if (!issueTitle.trim() || !issueAnnotatorId.trim()) {
      toast.error("Title and annotator are required");
      return;
    }
    setIssuing(true);
    try {
      const body: CertificateCreateBody = {
        annotator_id: issueAnnotatorId,
        title: issueTitle,
        description: issueDesc,
        certificate_type: issueType,
      };
      const newCert = await api.issueCertificate(body);
      setAllCerts((prev) => [newCert, ...prev]);
      toast.success(`Certificate issued to ${newCert.recipient_name}`);
      setShowIssue(false);
      setIssueTitle("");
      setIssueDesc("");
      setIssueAnnotatorId("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to issue certificate");
    } finally {
      setIssuing(false);
    }
  }

  function openPublicPage(certId: string) {
    window.open(`/certificate/${certId}`, "_blank");
  }

  function copyLink(certId: string) {
    const url = `${window.location.origin}/certificate/${certId}`;
    navigator.clipboard.writeText(url).then(
      () => toast.success("Certificate link copied"),
      () => toast.error("Failed to copy link")
    );
  }

  if (!user || !sessionId) return null;

  return (
    <AppShell>
      <header className="card" style={{ padding: 16, display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
        <div>
          <h1 style={{ margin: 0 }}>My Certificates</h1>
          <p style={{ margin: "6px 0 0", color: "var(--muted)" }}>
            Certificates earned through course completions and exams
          </p>
        </div>
      </header>

      {loading ? (
        <p style={{ marginTop: 18, color: "var(--muted)", textAlign: "center" }}>Loading certificates...</p>
      ) : certs.length === 0 ? (
        <div className="card" style={{ marginTop: 18, padding: 32, textAlign: "center" }}>
          <p style={{ fontSize: 48, margin: "0 0 12px" }}>📜</p>
          <h2 style={{ margin: "0 0 8px" }}>No certificates yet</h2>
          <p style={{ color: "var(--muted)", maxWidth: 400, margin: "0 auto" }}>
            Complete courses and pass exams to earn certificates. They will appear here.
          </p>
        </div>
      ) : (
        <div style={{ marginTop: 18, display: "grid", gap: 12 }}>
          {certs.map((c) => (
            <CertCard key={c.id} cert={c} onOpen={openPublicPage} onCopy={copyLink} />
          ))}
        </div>
      )}

      {isAdmin && (
        <>
          <section className="card" style={{ marginTop: 32, padding: 16 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <h2 style={{ margin: 0 }}>Admin: All Certificates</h2>
              <button className="btn btn-primary" onClick={() => setShowIssue(!showIssue)}>
                {showIssue ? "Cancel" : "Issue Certificate"}
              </button>
            </div>

            {showIssue && (
              <div className="card" style={{ padding: 16, marginBottom: 16, border: "2px solid var(--primary-light)" }}>
                <h3 style={{ marginTop: 0 }}>Issue New Certificate</h3>
                <div style={{ display: "grid", gap: 12, maxWidth: 480 }}>
                  <label style={{ display: "grid", gap: 4 }}>
                    <span style={{ fontSize: 13, color: "var(--muted)" }}>Annotator</span>
                    {members.length > 0 ? (
                      <select className="input" value={issueAnnotatorId} onChange={(e) => setIssueAnnotatorId(e.target.value)}>
                        <option value="">Select annotator...</option>
                        {members.map((m) => (
                          <option key={m.id} value={m.id}>{m.name} ({m.email})</option>
                        ))}
                      </select>
                    ) : (
                      <input className="input" placeholder="Annotator UUID" value={issueAnnotatorId} onChange={(e) => setIssueAnnotatorId(e.target.value)} />
                    )}
                  </label>
                  <label style={{ display: "grid", gap: 4 }}>
                    <span style={{ fontSize: 13, color: "var(--muted)" }}>Title</span>
                    <input className="input" placeholder="e.g. RLHF Annotation Fundamentals" value={issueTitle} onChange={(e) => setIssueTitle(e.target.value)} />
                  </label>
                  <label style={{ display: "grid", gap: 4 }}>
                    <span style={{ fontSize: 13, color: "var(--muted)" }}>Description (optional)</span>
                    <textarea className="input" rows={2} placeholder="Details about this certificate" value={issueDesc} onChange={(e) => setIssueDesc(e.target.value)} />
                  </label>
                  <label style={{ display: "grid", gap: 4 }}>
                    <span style={{ fontSize: 13, color: "var(--muted)" }}>Type</span>
                    <select className="input" value={issueType} onChange={(e) => setIssueType(e.target.value)}>
                      <option value="course_completion">Course Completion</option>
                      <option value="exam_passed">Exam Passed</option>
                      <option value="achievement">Achievement</option>
                    </select>
                  </label>
                  <button className="btn btn-primary" disabled={issuing} onClick={handleIssue} style={{ justifySelf: "start" }}>
                    {issuing ? "Issuing..." : "Issue Certificate"}
                  </button>
                </div>
              </div>
            )}

            {allLoading ? (
              <p style={{ color: "var(--muted)" }}>Loading...</p>
            ) : allCerts.length === 0 ? (
              <p style={{ color: "var(--muted)" }}>No certificates have been issued yet.</p>
            ) : (
              <div style={{ display: "grid", gap: 10 }}>
                {allCerts.map((c) => (
                  <CertCard key={c.id} cert={c} onOpen={openPublicPage} onCopy={copyLink} showRecipient />
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </AppShell>
  );
}

function CertCard({
  cert,
  onOpen,
  onCopy,
  showRecipient,
}: {
  cert: CertificateRead;
  onOpen: (id: string) => void;
  onCopy: (id: string) => void;
  showRecipient?: boolean;
}) {
  const typeColors: Record<string, { bg: string; fg: string }> = {
    course_completion: { bg: "#dbeafe", fg: "#1e40af" },
    exam_passed: { bg: "#d1fae5", fg: "#065f46" },
    achievement: { bg: "#fef3c7", fg: "#92400e" },
  };
  const colors = typeColors[cert.certificate_type] ?? { bg: "#e2e8f0", fg: "#334155" };

  return (
    <article
      className="card"
      style={{
        padding: 16,
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        gap: 16,
        flexWrap: "wrap",
      }}
    >
      <div style={{ minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <span
            style={{
              display: "inline-block",
              padding: "2px 10px",
              borderRadius: 12,
              fontSize: 11,
              fontWeight: 600,
              background: colors.bg,
              color: colors.fg,
            }}
          >
            {cert.certificate_type.replace(/_/g, " ")}
          </span>
        </div>
        <h3 style={{ margin: "4px 0 2px", fontSize: 16 }}>{cert.title}</h3>
        {showRecipient && (
          <p style={{ margin: "0 0 2px", fontSize: 14, fontWeight: 600 }}>{cert.recipient_name}</p>
        )}
        {cert.description && (
          <p style={{ margin: "0 0 4px", fontSize: 13, color: "var(--muted)" }}>{cert.description}</p>
        )}
        <p style={{ margin: 0, fontSize: 12, color: "var(--muted)" }}>
          Issued {new Date(cert.issued_at).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" })}
        </p>
      </div>
      <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
        <button className="btn" onClick={() => onCopy(cert.id)} style={{ fontSize: 13 }}>
          Copy Link
        </button>
        <button className="btn btn-primary" onClick={() => onOpen(cert.id)} style={{ fontSize: 13 }}>
          View
        </button>
      </div>
    </article>
  );
}
