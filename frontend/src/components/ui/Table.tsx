"use client";

import type { ReactNode } from "react";

export interface Column<T> {
  key: string;
  header: string;
  render?: (value: unknown, row: T) => ReactNode;
  width?: string;
}

export interface TableProps<T> {
  columns: Column<T>[];
  data: T[];
  loading?: boolean;
  emptyMessage?: string;
  onRowClick?: (row: T) => void;
}

function cellValue<T extends object>(row: T, key: string): unknown {
  return (row as Record<string, unknown>)[key];
}

export function Table<T extends object>({
  columns,
  data,
  loading,
  emptyMessage = "No data",
  onRowClick
}: TableProps<T>) {
  if (loading) {
    return (
      <p style={{ margin: 0, padding: "20px 0", color: "#64748b", fontSize: 14 }}>Loading…</p>
    );
  }
  if (!data.length) {
    return (
      <p style={{ margin: 0, padding: "20px 0", color: "#64748b", fontSize: 14 }}>{emptyMessage}</p>
    );
  }
  return (
    <div style={{ overflowX: "auto" }}>
      <table
        style={{
          width: "100%",
          borderCollapse: "collapse",
          fontSize: 14
        }}
      >
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                style={{
                  textAlign: "left",
                  padding: "10px 8px",
                  borderBottom: "1px solid #e5e7eb",
                  color: "#64748b",
                  fontWeight: 600,
                  fontSize: 12,
                  textTransform: "uppercase",
                  letterSpacing: "0.02em",
                  width: col.width,
                  whiteSpace: "nowrap"
                }}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, ri) => {
            const rk = `${ri}-${columns.map((c) => String(cellValue(row, c.key))).join("-")}`;
            return (
              <tr
                key={rk}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                style={{
                  cursor: onRowClick ? "pointer" : undefined,
                  background: ri % 2 === 0 ? "#ffffff" : "#f9fafb"
                }}
              >
                {columns.map((col) => {
                  const v = cellValue(row, col.key);
                  const content = col.render ? col.render(v, row) : (v as ReactNode);
                  return (
                    <td
                      key={col.key}
                      style={{
                        padding: "10px 8px",
                        borderBottom: "1px solid #e5e7eb",
                        verticalAlign: "middle",
                        maxWidth: col.width ? col.width : 320,
                        wordBreak: "break-word"
                      }}
                    >
                      {content as ReactNode}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
