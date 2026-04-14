"use client";

import { EXAM_REVIEW_RUBRIC_CRITERIA } from "@/lib/examReviewRubric";

const SCALE = [1, 2, 3, 4, 5] as const;

type Props = {
  value: Record<string, number | undefined>;
  onChange: (criterionId: string, score: number) => void;
  disabled?: boolean;
};

export function ExamReviewRubric({ value, onChange, disabled }: Props) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {EXAM_REVIEW_RUBRIC_CRITERIA.map((c) => (
        <div key={c.id}>
          <div style={{ fontWeight: 700, fontSize: 14, color: "var(--foreground, #1e293b)" }}>{c.title}</div>
          <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 4, lineHeight: 1.45 }}>{c.description}</div>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 8,
              marginTop: 10,
              alignItems: "center"
            }}
          >
            {SCALE.map((n) => {
              const selected = value[c.id] === n;
              return (
                <button
                  key={n}
                  type="button"
                  disabled={disabled}
                  onClick={() => onChange(c.id, n)}
                  style={{
                    minWidth: 40,
                    padding: "8px 12px",
                    borderRadius: 8,
                    border: selected ? "2px solid var(--primary, #2563eb)" : "1px solid var(--border)",
                    background: selected ? "rgba(37, 99, 235, 0.08)" : "var(--card, #fff)",
                    color: "inherit",
                    fontWeight: selected ? 700 : 500,
                    cursor: disabled ? "not-allowed" : "pointer",
                    fontSize: 14
                  }}
                >
                  {n}
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
