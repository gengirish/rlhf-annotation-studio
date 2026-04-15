"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";

import type { CertificatePublic } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

export default function CertificatePublicPage() {
  const { id } = useParams<{ id: string }>();
  const [cert, setCert] = useState<CertificatePublic | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const certRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`${API_BASE}/api/v1/certificates/${encodeURIComponent(id)}/public`);
        if (!res.ok) {
          const body = (await res.json().catch(() => ({}))) as { detail?: string };
          throw new Error(body.detail || "Certificate not found");
        }
        setCert(await res.json());
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load certificate");
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, [id]);

  function handlePrint() {
    window.print();
  }

  if (loading) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#f0f2f5" }}>
        <p style={{ color: "#64748b", fontSize: 18 }}>Loading certificate...</p>
      </div>
    );
  }

  if (error || !cert) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#f0f2f5" }}>
        <div style={{ textAlign: "center" }}>
          <h1 style={{ fontSize: 28, marginBottom: 8, color: "#1e293b" }}>Certificate Not Found</h1>
          <p style={{ color: "#64748b" }}>{error || "This certificate does not exist or has been revoked."}</p>
        </div>
      </div>
    );
  }

  const issuedDate = new Date(cert.issued_at).toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  const typeLabel =
    cert.certificate_type === "exam_passed" ? "Exam Achievement" :
    cert.certificate_type === "course_completion" ? "Course Completion" :
    "Completion";

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
        padding: "40px 20px",
      }}
    >
      <div
        ref={certRef}
        style={{
          width: "100%",
          maxWidth: 820,
          background: "#ffffff",
          borderRadius: 16,
          boxShadow: "0 25px 60px rgba(0,0,0,0.15)",
          overflow: "hidden",
          position: "relative",
        }}
      >
        {/* Top accent bar */}
        <div
          style={{
            height: 6,
            background: "linear-gradient(90deg, #6366f1, #a855f7, #ec4899)",
          }}
        />

        <div style={{ padding: "60px 48px 50px", textAlign: "center", position: "relative" }}>
          {/* Corner decorations */}
          <div style={{ position: "absolute", top: 20, left: 20, opacity: 0.08, fontSize: 120, lineHeight: 1, color: "#6366f1" }}>
            ◆
          </div>
          <div style={{ position: "absolute", bottom: 20, right: 20, opacity: 0.08, fontSize: 120, lineHeight: 1, color: "#6366f1" }}>
            ◆
          </div>

          {/* Logo / brand */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 10, marginBottom: 32 }}>
            <span style={{ fontSize: 28, color: "#6366f1" }}>◆</span>
            <span style={{ fontSize: 18, fontWeight: 700, letterSpacing: 1.5, color: "#1e293b", textTransform: "uppercase" }}>
              RLHF Annotation Studio
            </span>
          </div>

          {/* Certificate type label */}
          <p
            style={{
              fontSize: 13,
              fontWeight: 600,
              letterSpacing: 3,
              textTransform: "uppercase",
              color: "#6366f1",
              marginBottom: 8,
            }}
          >
            Certificate of {typeLabel}
          </p>

          {/* Divider */}
          <div style={{ width: 80, height: 2, background: "linear-gradient(90deg, transparent, #6366f1, transparent)", margin: "0 auto 24px" }} />

          <p style={{ fontSize: 15, color: "#64748b", marginBottom: 8 }}>
            This is to certify that
          </p>

          {/* Recipient name */}
          <h1
            style={{
              fontSize: 42,
              fontWeight: 700,
              color: "#1e293b",
              margin: "8px 0 16px",
              fontFamily: "Georgia, 'Times New Roman', serif",
            }}
          >
            {cert.recipient_name}
          </h1>

          {/* Divider under name */}
          <div style={{ width: 200, height: 1, background: "#e2e8f0", margin: "0 auto 20px" }} />

          <p style={{ fontSize: 16, color: "#475569", lineHeight: 1.6, maxWidth: 560, margin: "0 auto 8px" }}>
            has successfully completed
          </p>

          {/* Certificate title */}
          <h2 style={{ fontSize: 24, fontWeight: 600, color: "#1e293b", margin: "8px 0 16px" }}>
            {cert.title}
          </h2>

          {/* Description */}
          {cert.description && (
            <p style={{ fontSize: 14, color: "#64748b", lineHeight: 1.6, maxWidth: 500, margin: "0 auto 24px" }}>
              {cert.description}
            </p>
          )}

          {/* Issue date */}
          <div
            style={{
              marginTop: 32,
              paddingTop: 24,
              borderTop: "1px solid #e2e8f0",
              display: "flex",
              justifyContent: "center",
              alignItems: "center",
              gap: 48,
            }}
          >
            <div style={{ textAlign: "center" }}>
              <p style={{ fontSize: 12, color: "#94a3b8", textTransform: "uppercase", letterSpacing: 1, marginBottom: 4 }}>
                Date Issued
              </p>
              <p style={{ fontSize: 15, fontWeight: 600, color: "#1e293b" }}>
                {issuedDate}
              </p>
            </div>
            <div style={{ textAlign: "center" }}>
              <p style={{ fontSize: 12, color: "#94a3b8", textTransform: "uppercase", letterSpacing: 1, marginBottom: 4 }}>
                Certificate ID
              </p>
              <p style={{ fontSize: 13, fontWeight: 500, color: "#64748b", fontFamily: "monospace" }}>
                {cert.id.slice(0, 8)}
              </p>
            </div>
          </div>
        </div>

        {/* Bottom accent bar */}
        <div
          style={{
            height: 6,
            background: "linear-gradient(90deg, #ec4899, #a855f7, #6366f1)",
          }}
        />
      </div>

      {/* Actions below the card */}
      <div style={{ marginTop: 24, display: "flex", gap: 12 }} className="no-print">
        <button
          onClick={handlePrint}
          style={{
            padding: "12px 28px",
            fontSize: 15,
            fontWeight: 600,
            color: "#fff",
            background: "#6366f1",
            border: "none",
            borderRadius: 8,
            cursor: "pointer",
            boxShadow: "0 4px 14px rgba(99,102,241,0.4)",
            transition: "transform 0.15s, box-shadow 0.15s",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = "translateY(-1px)";
            e.currentTarget.style.boxShadow = "0 6px 20px rgba(99,102,241,0.5)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = "translateY(0)";
            e.currentTarget.style.boxShadow = "0 4px 14px rgba(99,102,241,0.4)";
          }}
        >
          Download Certificate
        </button>
      </div>

      {/* Print-only footer */}
      <div style={{ marginTop: 16, textAlign: "center" }} className="no-print">
        <p style={{ fontSize: 13, color: "rgba(255,255,255,0.7)" }}>
          Verify this certificate at{" "}
          <span style={{ fontFamily: "monospace", color: "rgba(255,255,255,0.9)" }}>
            {typeof window !== "undefined" ? window.location.href : ""}
          </span>
        </p>
      </div>

      <style>{`
        @media print {
          .no-print { display: none !important; }
          body { background: white !important; }
        }
      `}</style>
    </div>
  );
}
