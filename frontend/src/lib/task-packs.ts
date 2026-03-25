import type { TaskItem } from "@/types";

import { api } from "@/lib/api";

export async function fetchTaskPack(slug: string): Promise<TaskItem[]> {
  const pack = await api.getTaskPack(slug);
  return pack.tasks_json;
}
