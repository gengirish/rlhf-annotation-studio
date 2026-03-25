import type { TaskItem } from "@/types";

export async function fetchTaskPack(fileName: string): Promise<TaskItem[]> {
  const res = await fetch(`/api/task-packs/${encodeURIComponent(fileName)}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Unable to load task pack: ${fileName}`);
  }
  return (await res.json()) as TaskItem[];
}
