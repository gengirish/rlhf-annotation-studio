import { readFile } from "node:fs/promises";
import { join } from "node:path";

import { NextResponse } from "next/server";

const ALLOWED = new Set([
  "debugging-exercises-python.json",
  "debugging-exercises-java.json",
  "code-review-comparisons.json",
  "safety-alignment.json"
]);

export async function GET(_: Request, context: { params: { file: string } }) {
  const file = context.params.file;
  if (!ALLOWED.has(file)) {
    return NextResponse.json({ detail: "Task pack not found" }, { status: 404 });
  }

  try {
    const absolute = join(process.cwd(), "..", "tasks", file);
    const json = await readFile(absolute, "utf8");
    return new NextResponse(json, { headers: { "content-type": "application/json" } });
  } catch {
    return NextResponse.json({ detail: "Task pack read failed" }, { status: 500 });
  }
}
