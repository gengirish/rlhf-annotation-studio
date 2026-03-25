import type { TaskItem, WorkspaceSnapshot } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = typeof window !== "undefined" ? localStorage.getItem("rlhf_authToken") : null;
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {})
    }
  });

  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new ApiError(res.status, body.detail || "Request failed");
  }

  return (await res.json()) as T;
}

export interface AuthResponse {
  token: string;
  annotator: { id: string; name: string; email: string; phone?: string | null };
  session_id: string;
}

export const api = {
  register: (body: { name: string; email: string; password: string; phone?: string }) =>
    request<AuthResponse>("/api/v1/auth/register", { method: "POST", body: JSON.stringify(body) }),
  login: (body: { email: string; password: string }) =>
    request<AuthResponse>("/api/v1/auth/login", { method: "POST", body: JSON.stringify(body) }),
  health: () => request<{ status: string }>("/api/v1/health"),
  inferenceStatus: () =>
    request<{ enabled: boolean; configured: boolean; require_auth: boolean }>("/api/v1/inference/status"),
  inferenceModels: () => request<{ default: string; models: string[] }>("/api/v1/inference/models"),
  inferenceStream: async (body: { prompt: string; model?: string; system?: string }) =>
    fetch(`${API_BASE}/api/v1/inference/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(localStorage.getItem("rlhf_authToken")
          ? { Authorization: `Bearer ${localStorage.getItem("rlhf_authToken")}` }
          : {})
      },
      body: JSON.stringify(body)
    }),
  getWorkspace: (sessionId: string) =>
    request<{
      session_id: string;
      annotator_id: string;
      tasks: TaskItem[] | null;
      annotations: WorkspaceSnapshot["annotations"];
      task_times: WorkspaceSnapshot["task_times"];
      active_pack_file: string | null;
    }>(`/api/v1/sessions/${sessionId}/workspace`),
  putWorkspace: (sessionId: string, body: WorkspaceSnapshot) =>
    request<{ ok: boolean }>(`/api/v1/sessions/${sessionId}/workspace`, {
      method: "PUT",
      body: JSON.stringify(body)
    }),
  validateTasks: (tasks: TaskItem[]) =>
    request<{ ok: boolean; issues: Array<{ row_index: number; row_label: string; message: string }> }>(
      "/api/v1/tasks/validate",
      { method: "POST", body: JSON.stringify({ tasks, strict_mode: false }) }
    ),
  getTaskPacks: () =>
    request<{ packs: TaskPackSummary[] }>("/api/v1/tasks/packs"),
  getTaskPack: (slug: string) =>
    request<TaskPackDetail>(`/api/v1/tasks/packs/${encodeURIComponent(slug)}`)
};

export interface TaskPackSummary {
  id: string;
  slug: string;
  name: string;
  description: string;
  language: string;
  task_count: number;
  created_at: string;
}

export interface TaskPackDetail extends TaskPackSummary {
  tasks_json: TaskItem[];
}
