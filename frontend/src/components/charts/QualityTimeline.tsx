"use client";

export interface QualityTimelineProps {
  dataPoints: { date: string; score: number }[];
  height?: number;
  width?: number;
}

export function QualityTimeline({ dataPoints, height = 120, width = 400 }: QualityTimelineProps) {
  if (!dataPoints.length) {
    return (
      <div
        style={{
          height,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#94a3b8",
          fontSize: 13,
          border: "1px dashed #e5e7eb",
          borderRadius: 8,
          background: "#f9fafb"
        }}
      >
        No timeline data
      </div>
    );
  }

  const scores = dataPoints.map((d) => d.score);
  const min = Math.min(...scores, 0);
  const max = Math.max(...scores, 1);
  const span = max - min || 1;
  const pad = 12;
  const w = width - pad * 2;
  const h = height - pad * 2;

  const pts = dataPoints.map((d, i) => {
    const x = pad + (dataPoints.length === 1 ? w / 2 : (i / (dataPoints.length - 1)) * w);
    const y = pad + h - ((d.score - min) / span) * h;
    return `${x},${y}`;
  });

  const last = dataPoints[dataPoints.length - 1];
  const first = dataPoints[0];

  return (
    <div style={{ width: "100%", maxWidth: width }}>
      <svg
        width="100%"
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label={`Quality from ${first.date} to ${last.date}`}
      >
        <defs>
          <linearGradient id="ql_fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#6366f1" stopOpacity="0.25" />
            <stop offset="100%" stopColor="#6366f1" stopOpacity="0" />
          </linearGradient>
        </defs>
        <rect x={0} y={0} width={width} height={height} fill="#f9fafb" rx="8" />
        <polyline
          fill="none"
          stroke="#e5e7eb"
          strokeWidth={1}
          points={`${pad},${pad + h} ${pad + w},${pad + h}`}
        />
        <polygon fill="url(#ql_fill)" points={`${pts.join(" ")} ${pad + w},${pad + h} ${pad},${pad + h}`} />
        <polyline fill="none" stroke="#6366f1" strokeWidth={2.5} strokeLinejoin="round" strokeLinecap="round" points={pts.join(" ")} />
        {dataPoints.map((d, i) => {
          const x = pad + (dataPoints.length === 1 ? w / 2 : (i / (dataPoints.length - 1)) * w);
          const y = pad + h - ((d.score - min) / span) * h;
          return <circle key={`${d.date}-${i}`} cx={x} cy={y} r={3.5} fill="#fff" stroke="#6366f1" strokeWidth={2} />;
        })}
      </svg>
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6, fontSize: 11, color: "#64748b" }}>
        <span>{first.date}</span>
        <span>{last.date}</span>
      </div>
    </div>
  );
}
