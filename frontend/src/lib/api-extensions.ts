import { ApiError } from "@/lib/api";
import type {
  HumanOverrideRequest,
  JudgeBatchResponse,
  JudgeEvaluateRequest,
  LLMEvaluation
} from "@/types/extensions";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = typeof window !== "undefined" ? localStorage.getItem("rlhf_authToken") : null;
  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {})
    }
  });

  if (res.status === 204) {
    return undefined as T;
  }

  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new ApiError(res.status, body.detail || "Request failed");
  }

  const text = await res.text();
  if (!text) {
    return undefined as T;
  }
  return JSON.parse(text) as T;
}

const Q = "/api/v1/quality";

export const qualityApi = {
  getScore: (annotatorId: string) => apiFetch<unknown>(`${Q}/score/${encodeURIComponent(annotatorId)}`),
  getLeaderboard: () => apiFetch<unknown>(`${Q}/leaderboard`),
  getDashboard: () => apiFetch<unknown>(`${Q}/dashboard`),
  getDrift: (annotatorId: string) => apiFetch<unknown>(`${Q}/drift/${encodeURIComponent(annotatorId)}`),
  listDriftAlerts: (annotatorId?: string) => {
    if (!annotatorId) return Promise.resolve([]);
    return apiFetch<unknown>(`${Q}/drift/${encodeURIComponent(annotatorId)}`);
  },
  getCalibrationTests: () => apiFetch<unknown>(`${Q}/calibration`),
  createCalibrationTest: (data: Record<string, unknown>) =>
    apiFetch<unknown>(`${Q}/calibration`, { method: "POST", body: JSON.stringify(data) })
};

const D = "/api/v1/datasets";

export const datasetApi = {
  list: (params?: { skip?: number; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.skip !== undefined) qs.set("skip", String(params.skip));
    if (params?.limit !== undefined) qs.set("limit", String(params.limit));
    const q = qs.toString();
    return apiFetch<unknown>(`${D}${q ? `?${q}` : ""}`);
  },
  get: (id: string) => apiFetch<unknown>(`${D}/${encodeURIComponent(id)}`),
  create: (data: Record<string, unknown>) =>
    apiFetch<unknown>(D, { method: "POST", body: JSON.stringify(data) }),
  createVersion: (id: string, data: Record<string, unknown>) =>
    apiFetch<unknown>(`${D}/${encodeURIComponent(id)}/versions`, {
      method: "POST",
      body: JSON.stringify(data)
    }),
  exportVersion: (id: string, version: number, format: string) =>
    apiFetch<unknown>(
      `${D}/${encodeURIComponent(id)}/versions/${version}/export?format=${encodeURIComponent(format)}`
    ),
  diff: (id: string, v1: number, v2: number) =>
    apiFetch<unknown>(
      `${D}/${encodeURIComponent(id)}/diff?v1=${v1}&v2=${v2}`
    ),
  delete: (id: string) =>
    apiFetch<void>(`${D}/${encodeURIComponent(id)}`, { method: "DELETE" })
};

const W = "/api/v1/webhooks";

export const webhookApi = {
  list: () => apiFetch<unknown[]>(W),
  get: (id: string) => apiFetch<unknown>(`${W}/${encodeURIComponent(id)}`),
  create: (data: Record<string, unknown>) =>
    apiFetch<unknown>(W, { method: "POST", body: JSON.stringify(data) }),
  update: (id: string, data: Record<string, unknown>) =>
    apiFetch<unknown>(`${W}/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(data)
    }),
  delete: (id: string) =>
    apiFetch<void>(`${W}/${encodeURIComponent(id)}`, { method: "DELETE" }),
  deliveries: (id: string, params?: { skip?: number; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.skip !== undefined) qs.set("skip", String(params.skip));
    if (params?.limit !== undefined) qs.set("limit", String(params.limit));
    const q = qs.toString();
    return apiFetch<unknown[]>(`${W}/${encodeURIComponent(id)}/deliveries${q ? `?${q}` : ""}`);
  },
  test: (id: string, body?: { event?: string }) =>
    apiFetch<unknown>(`${W}/${encodeURIComponent(id)}/test`, {
      method: "POST",
      body: JSON.stringify(body ?? {})
    })
};

const A = "/api/v1/audit";

export const auditApi = {
  listLogs: (params?: Record<string, string | number | undefined>) => {
    const qs = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== "") qs.set(k, String(v));
      });
    }
    return apiFetch<unknown>(`${A}/logs?${qs.toString()}`);
  },
  myActivity: (limit?: number) => {
    const qs = new URLSearchParams();
    if (limit !== undefined) qs.set("limit", String(limit));
    return apiFetch<unknown[]>(`${A}/logs/me?${qs.toString()}`);
  },
  resourceHistory: (resourceType: string, resourceId: string) =>
    apiFetch<unknown[]>(`${A}/logs/resource/${encodeURIComponent(resourceType)}/${encodeURIComponent(resourceId)}`),
  stats: () => apiFetch<unknown>(`${A}/stats`)
};

const I = "/api/v1/iaa";

export const iaaApi = {
  compute: (body: Record<string, unknown>) =>
    apiFetch<unknown>(`${I}/compute`, { method: "POST", body: JSON.stringify(body) }),
  summary: (taskPackId: string) => apiFetch<unknown>(`${I}/summary/${encodeURIComponent(taskPackId)}`)
};

const J = "/api/v1/judge";

export const judgeApi = {
  evaluate: (body: JudgeEvaluateRequest) =>
    apiFetch<JudgeBatchResponse>(`${J}/evaluate`, { method: "POST", body: JSON.stringify(body) }),
  listEvaluations: (taskPackId: string) =>
    apiFetch<LLMEvaluation[]>(`${J}/evaluations/${encodeURIComponent(taskPackId)}`),
  getEvaluation: (taskPackId: string, taskId: string) =>
    apiFetch<LLMEvaluation>(
      `${J}/evaluations/${encodeURIComponent(taskPackId)}/${encodeURIComponent(taskId)}`
    ),
  overrideEvaluation: (evaluationId: string, body: HumanOverrideRequest) =>
    apiFetch<LLMEvaluation>(`${J}/evaluations/${encodeURIComponent(evaluationId)}/override`, {
      method: "POST",
      body: JSON.stringify(body)
    }),
  acceptEvaluation: (evaluationId: string) =>
    apiFetch<LLMEvaluation>(`${J}/evaluations/${encodeURIComponent(evaluationId)}/accept`, {
      method: "POST"
    }),
  rejectEvaluation: (evaluationId: string) =>
    apiFetch<LLMEvaluation>(`${J}/evaluations/${encodeURIComponent(evaluationId)}/reject`, {
      method: "POST"
    })
};

const C = "/api/v1/consensus";

export const consensusApi = {
  listTasks: (taskPackId?: string) => {
    const qs = new URLSearchParams();
    if (taskPackId) qs.set("task_pack_id", taskPackId);
    const q = qs.toString();
    return apiFetch<unknown[]>(`${C}/tasks${q ? `?${q}` : ""}`);
  },
  getTask: (id: string) => apiFetch<unknown>(`${C}/tasks/${encodeURIComponent(id)}`),
  resolve: (id: string, body: Record<string, unknown>) =>
    apiFetch<unknown>(`${C}/tasks/${encodeURIComponent(id)}/resolve`, {
      method: "POST",
      body: JSON.stringify(body)
    })
};
