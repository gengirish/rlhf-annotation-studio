import Link from "next/link";

const FEATURES = [
  {
    icon: "✎",
    title: "Multi-format Annotation",
    desc: "Comparison, rating, and ranking tasks with streaming AI response simulation. Purpose-built for RLHF preference data."
  },
  {
    icon: "◎",
    title: "Quality Assurance",
    desc: "Gold-standard scoring, calibration tests, inter-annotator agreement, and real-time drift detection."
  },
  {
    icon: "⚡",
    title: "LLM-as-Judge",
    desc: "Automated batch evaluation with human override. Scale annotation quality without scaling headcount."
  },
  {
    icon: "▤",
    title: "Dataset Versioning",
    desc: "Version, diff, and export annotated datasets in JSONL, CSV, or HuggingFace format. Full audit trail."
  },
  {
    icon: "◉",
    title: "Team & RBAC",
    desc: "Multi-org support with admin, reviewer, and annotator roles. Bulk assignment and review workflows."
  },
  {
    icon: "⇄",
    title: "API-first + SDK",
    desc: "Full REST API, Python SDK, and CLI. Automate pipelines with webhooks and API keys."
  }
];

export default function LandingPage() {
  return (
    <div className="landing-hero">
      <nav className="landing-nav">
        <span className="shell-logo" style={{ color: "var(--primary)" }}>
          <span className="shell-logo-icon">◆</span>
          <span>RLHF Studio</span>
        </span>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <Link href="/auth" className="btn" style={{ fontSize: 14 }}>
            Login
          </Link>
          <Link href="/auth" className="btn btn-primary" style={{ fontSize: 14 }}>
            Get Started
          </Link>
        </div>
      </nav>

      <div className="landing-hero-inner">
        <span className="landing-badge">Open-source RLHF platform</span>
        <h1 className="landing-h1">
          Ship <em>better AI</em> with human feedback at scale
        </h1>
        <p className="landing-sub">
          The annotation platform purpose-built for RLHF. Collect preference data, ensure quality
          with gold scoring and IAA, and automate with LLM-as-judge — all in one tool.
        </p>
        <div className="landing-cta-row">
          <Link href="/auth" className="btn btn-primary landing-cta">
            Start Annotating
          </Link>
          <a
            href="https://github.com/gengirish/rlhf-annotation-studio"
            target="_blank"
            rel="noopener noreferrer"
            className="btn landing-cta"
          >
            View on GitHub
          </a>
        </div>
      </div>

      <section className="landing-features">
        {FEATURES.map((f) => (
          <article key={f.title} className="landing-feat">
            <div className="landing-feat-icon">{f.icon}</div>
            <h3>{f.title}</h3>
            <p>{f.desc}</p>
          </article>
        ))}
      </section>

      <section className="landing-stats">
        <div>
          <div className="landing-stat-val">3</div>
          <div className="landing-stat-label">Annotation formats</div>
        </div>
        <div>
          <div className="landing-stat-val">16+</div>
          <div className="landing-stat-label">API endpoints</div>
        </div>
        <div>
          <div className="landing-stat-val">100%</div>
          <div className="landing-stat-label">Open source</div>
        </div>
        <div>
          <div className="landing-stat-val">SDK</div>
          <div className="landing-stat-label">Python + CLI</div>
        </div>
      </section>

      <footer className="landing-footer">
        RLHF Annotation Studio — Open source, built for AI teams
      </footer>
    </div>
  );
}
