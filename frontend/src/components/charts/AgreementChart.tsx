"use client";

export interface AgreementChartProps {
  dimensions: { name: string; score: number; threshold?: number }[];
  height?: number;
}

function normScore(score: number): number {
  if (score > 1) return Math.min(1, score / 100);
  return Math.max(0, Math.min(1, score));
}

function barColor(score: number, threshold?: number): string {
  const s = normScore(score);
  const t = threshold !== undefined ? normScore(threshold) : undefined;
  if (t === undefined) return s >= 0.7 ? "#10b981" : s >= 0.5 ? "#f59e0b" : "#ef4444";
  if (s >= t) return "#10b981";
  const close = t - s <= 0.08;
  return close ? "#f59e0b" : "#ef4444";
}

export function AgreementChart({ dimensions, height = 220 }: AgreementChartProps) {
  const rowH = Math.max(32, Math.floor((height - 24) / Math.max(dimensions.length, 1)));
  const totalH = 24 + dimensions.length * rowH;

  return (
    <div style={{ width: "100%" }}>
      <svg
        width="100%"
        height={totalH}
        viewBox={`0 0 400 ${totalH}`}
        preserveAspectRatio="none"
        style={{ display: "block", maxWidth: "100%" }}
        role="img"
        aria-label="Agreement scores by dimension"
      >
        <rect width="400" height={totalH} fill="#f9fafb" rx="8" />
        {dimensions.map((d, i) => {
          const y = 12 + i * rowH;
          const ns = normScore(d.score);
          const w = Math.min(100, Math.max(0, ns * 100));
          const fill = barColor(d.score, d.threshold);
          return (
            <g key={d.name}>
              <text x={8} y={y + rowH / 2 + 4} fontSize={11} fill="#475569" fontFamily="system-ui, sans-serif">
                {d.name.length > 18 ? `${d.name.slice(0, 16)}…` : d.name}
              </text>
              <rect x={120} y={y + 6} width={260} height={rowH - 12} fill="#e5e7eb" rx={4} />
              <rect x={120} y={y + 6} width={(260 * w) / 100} height={rowH - 12} fill={fill} rx={4} />
              <text
                x={388}
                y={y + rowH / 2 + 4}
                fontSize={11}
                fill="#0f172a"
                fontFamily="system-ui, sans-serif"
                textAnchor="end"
                fontWeight={600}
              >
                {(ns * 100).toFixed(0)}%
              </text>
            </g>
          );
        })}
      </svg>
      <div style={{ display: "flex", gap: 16, marginTop: 8, flexWrap: "wrap", fontSize: 12, color: "#64748b" }}>
        <span>
          <span style={{ color: "#10b981", fontWeight: 600 }}>■</span> At/above threshold
        </span>
        <span>
          <span style={{ color: "#f59e0b", fontWeight: 600 }}>■</span> Close
        </span>
        <span>
          <span style={{ color: "#ef4444", fontWeight: 600 }}>■</span> Below
        </span>
      </div>
    </div>
  );
}
