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
  annotator: {
    id: string;
    name: string;
    email: string;
    phone?: string | null;
    role?: string;
    org_id?: string | null;
  };
  session_id: string;
}

export interface InferenceModelOption {
  id: string;
  name: string;
  tag: string;
}

export interface QualityScore {
  total_gold_tasks: number;
  scored_tasks: number;
  overall_accuracy: number;
}

export interface SessionMetrics {
  total_tasks: number;
  completed_tasks: number;
  skipped_tasks: number;
  pending_tasks: number;
  completion_rate: number;
  avg_time_seconds: number;
  median_time_seconds: number;
  total_time_seconds: number;
  dimension_averages: Record<string, number>;
  tasks_by_type: Record<string, number>;
}

export interface TimelinePoint {
  revision_number: number;
  created_at: string;
  completed_count: number;
}

export interface SessionTimeline {
  points: TimelinePoint[];
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  plan_tier: string;
  max_seats: number;
  max_packs: number;
  created_at: string;
  used_seats?: number;
  used_packs?: number;
}

export interface OrgMember {
  id: string;
  name: string;
  email: string;
  role?: string;
}

export interface CreateOrgBody {
  name: string;
  slug: string;
}

export interface UpdateOrgBody {
  name?: string;
  slug?: string;
}

export interface AddOrgMemberBody {
  email: string;
}

export interface TaskPackUpsertBody {
  name: string;
  slug: string;
  description: string;
  language: string;
  tasks_json: TaskItem[];
}

export interface ReviewAssignment {
  id: string;
  task_pack_id: string;
  task_id: string;
  annotator_id: string;
  status: string;
  annotation_json: Record<string, unknown> | null;
  reviewer_id: string | null;
  reviewer_notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface TaskPackListResponse {
  packs: TaskPackSummary[];
  total?: number;
  limit?: number;
  offset?: number;
  has_more?: boolean;
}

export interface TaskSearchHit {
  pack_slug: string;
  pack_name: string;
  language: string;
  task_id: string;
  task_title: string;
  task_type: string;
  task_index: number;
}

export interface TaskSearchResponse {
  packs: TaskPackSummary[];
  tasks: TaskSearchHit[];
  query: string;
  total_packs: number;
  total_tasks: number;
}

export const api = {
  register: (body: { name: string; email: string; password: string; phone?: string; role?: string }) =>
    request<AuthResponse>("/api/v1/auth/register", { method: "POST", body: JSON.stringify(body) }),
  login: (body: { email: string; password: string }) =>
    request<AuthResponse>("/api/v1/auth/login", { method: "POST", body: JSON.stringify(body) }),
  health: () => request<{ status: string }>("/api/v1/health"),
  inferenceStatus: () =>
    request<{ enabled: boolean; configured: boolean; require_auth: boolean }>("/api/v1/inference/status"),
  inferenceModels: () =>
    request<{ default: string; models: InferenceModelOption[] }>("/api/v1/inference/models"),
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
  inferenceComplete: (body: {
    prompt: string;
    system?: string;
    slots: Array<{ label?: string; hf_model?: string; temperature?: number; seed?: number }>;
  }) =>
    request<{ slots: Array<{ label: string; text: string | null; model: string | null; error: string | null }> }>(
      "/api/v1/inference/complete",
      { method: "POST", body: JSON.stringify(body) }
    ),
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
  searchTasks: (params: { q: string; language?: string; task_type?: string; limit?: number }) => {
    const qs = new URLSearchParams();
    qs.set("q", params.q);
    if (params.language) qs.set("language", params.language);
    if (params.task_type) qs.set("task_type", params.task_type);
    if (params.limit !== undefined) qs.set("limit", String(params.limit));
    return request<TaskSearchResponse>(`/api/v1/tasks/search?${qs.toString()}`);
  },
  getTaskPacks: (params?: { limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.limit !== undefined) qs.set("limit", String(params.limit));
    if (params?.offset !== undefined) qs.set("offset", String(params.offset));
    const q = qs.toString();
    return request<TaskPackListResponse>(`/api/v1/tasks/packs${q ? `?${q}` : ""}`);
  },
  getAllTaskPacks: async (pageSize = 50): Promise<TaskPackSummary[]> => {
    let offset = 0;
    let all: TaskPackSummary[] = [];
    while (true) {
      const res = await request<TaskPackListResponse>(
        `/api/v1/tasks/packs?limit=${pageSize}&offset=${offset}`
      );
      const packs = Array.isArray(res.packs) ? res.packs : [];
      all = all.concat(packs);
      const hasMore = Boolean(res.has_more);
      if (!hasMore) break;
      offset += res.limit ?? pageSize;
    }
    return all;
  },
  getTaskPack: (slug: string) =>
    request<TaskPackDetail>(`/api/v1/tasks/packs/${encodeURIComponent(slug)}`),
  scoreSession: (sessionId: string) =>
    request<QualityScore>("/api/v1/tasks/score-session", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId })
    }),
  getSessionMetrics: (sessionId: string) =>
    request<SessionMetrics>(`/api/v1/metrics/session/${sessionId}/summary`),
  getSessionTimeline: (sessionId: string) =>
    request<SessionTimeline>(`/api/v1/metrics/session/${sessionId}/timeline`),
  getReviewQueue: () =>
    request<{ assignments: ReviewAssignment[] }>("/api/v1/reviews/queue"),
  getPendingReviews: () =>
    request<{ assignments: ReviewAssignment[] }>("/api/v1/reviews/pending"),
  updateReview: (assignmentId: string, body: { status: string; reviewer_notes?: string }) =>
    request<ReviewAssignment>(`/api/v1/reviews/${assignmentId}`, {
      method: "PUT",
      body: JSON.stringify(body)
    }),
  submitReview: (assignmentId: string, annotation: Record<string, unknown>) =>
    request<ReviewAssignment>(`/api/v1/reviews/${assignmentId}/submit`, {
      method: "POST",
      body: JSON.stringify({ annotation_json: annotation })
    }),
  getTeamReviews: (params?: { status?: string; annotator_id?: string }) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set("status", params.status);
    if (params?.annotator_id) qs.set("annotator_id", params.annotator_id);
    const q = qs.toString();
    return request<ReviewAssignment[]>(`/api/v1/reviews/team${q ? `?${q}` : ""}`);
  },
  bulkAssign: (body: { task_pack_id: string; annotator_id: string }) =>
    request<ReviewAssignment[]>("/api/v1/reviews/bulk-assign", {
      method: "POST",
      body: JSON.stringify(body)
    }),
  getWorkspaceHistory: (sessionId: string) =>
    request<{ revisions: Array<{ id: string; revision_number: number; created_at: string }> }>(
      `/api/v1/sessions/${sessionId}/workspace/history`
    ),
  getOrg: (orgId: string) =>
    request<Organization>(`/api/v1/orgs/${encodeURIComponent(orgId)}`),
  updateOrg: (orgId: string, body: UpdateOrgBody) =>
    request<Organization>(`/api/v1/orgs/${encodeURIComponent(orgId)}`, {
      method: "PUT",
      body: JSON.stringify(body)
    }),
  getOrgMembers: async (orgId: string): Promise<OrgMember[]> => {
    const r = await request<OrgMember[] | { members: OrgMember[] }>(
      `/api/v1/orgs/${encodeURIComponent(orgId)}/members`
    );
    return Array.isArray(r) ? r : r.members;
  },
  updateMemberRole: (orgId: string, memberId: string, role: string) =>
    request<OrgMember & { role: string }>(
      `/api/v1/orgs/${encodeURIComponent(orgId)}/members/${encodeURIComponent(memberId)}/role`,
      {
        method: "PUT",
        body: JSON.stringify({ role })
      }
    ),
  getTeamStats: (orgId: string) =>
    request<Array<{ annotator: OrgMember & { role: string }; stats: Record<string, number> }>>(
      `/api/v1/orgs/${encodeURIComponent(orgId)}/team-stats`
    ),
  createOrg: (body: CreateOrgBody) =>
    request<Organization>("/api/v1/orgs", { method: "POST", body: JSON.stringify(body) }),
  addOrgMember: (orgId: string, email: string) =>
    request<OrgMember>(`/api/v1/orgs/${encodeURIComponent(orgId)}/members`, {
      method: "POST",
      body: JSON.stringify({ email } satisfies AddOrgMemberBody)
    }),
  createTaskPack: (body: TaskPackUpsertBody) =>
    request<TaskPackDetail>("/api/v1/tasks/packs", {
      method: "POST",
      body: JSON.stringify(body)
    }),
  updateTaskPack: (slug: string, body: TaskPackUpsertBody) =>
    request<TaskPackDetail>(`/api/v1/tasks/packs/${encodeURIComponent(slug)}`, {
      method: "PUT",
      body: JSON.stringify(body)
    }),
  deleteTaskPack: async (slug: string) => {
    const token = typeof window !== "undefined" ? localStorage.getItem("rlhf_authToken") : null;
    const res = await fetch(`${API_BASE}/api/v1/tasks/packs/${encodeURIComponent(slug)}`, {
      method: "DELETE",
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {})
      }
    });
    if (!res.ok) {
      const body = (await res.json().catch(() => ({}))) as { detail?: string };
      throw new ApiError(res.status, body.detail || "Delete failed");
    }
  },

  getExams: () => request<ExamRead[]>("/api/v1/exams"),
  startExamAttempt: (examId: string) =>
    request<ExamAttemptStartResponse>(`/api/v1/exams/${encodeURIComponent(examId)}/attempts/start`, {
      method: "POST"
    }),
  getExamAttempt: (examId: string, attemptId: string) =>
    request<ExamAttemptRead>(
      `/api/v1/exams/${encodeURIComponent(examId)}/attempts/${encodeURIComponent(attemptId)}`
    ),
  saveExamAnswer: (
    examId: string,
    attemptId: string,
    body: { task_id: string; annotation_json: Record<string, unknown>; time_spent_seconds?: number }
  ) =>
    request<ExamAttemptRead>(
      `/api/v1/exams/${encodeURIComponent(examId)}/attempts/${encodeURIComponent(attemptId)}/answer`,
      {
        method: "PUT",
        body: JSON.stringify(body)
      }
    ),
  postExamIntegrityEvent: (
    examId: string,
    attemptId: string,
    body: { event_type: string; severity: "info" | "warn" | "high"; payload_json?: Record<string, unknown> }
  ) =>
    request<IntegrityEventRead>(
      `/api/v1/exams/${encodeURIComponent(examId)}/attempts/${encodeURIComponent(attemptId)}/integrity-events`,
      {
        method: "POST",
        body: JSON.stringify({
          event_type: body.event_type,
          severity: body.severity,
          payload_json: body.payload_json ?? {}
        })
      }
    ),
  submitExamAttempt: (examId: string, attemptId: string) =>
    request<ExamAttemptSubmitResponse>(
      `/api/v1/exams/${encodeURIComponent(examId)}/attempts/${encodeURIComponent(attemptId)}/submit`,
      { method: "POST" }
    ),
  getExamAttemptResult: (examId: string, attemptId: string) =>
    request<ExamResultRead>(
      `/api/v1/exams/${encodeURIComponent(examId)}/attempts/${encodeURIComponent(attemptId)}/result`
    ),
  getRubricCriteria: () =>
    request<Array<{ id: string; title: string; description: string }>>("/api/v1/exams/review/rubric-criteria"),
  getExamReviewAttempts: () => request<ReviewAttemptSummary[]>("/api/v1/exams/review/attempts"),
  releaseExamAttemptReview: (attemptId: string, body: ReviewReleaseRequest) =>
    request<ReviewReleaseResponse>(
      `/api/v1/exams/review/attempts/${encodeURIComponent(attemptId)}/release`,
      {
        method: "POST",
        body: JSON.stringify(body)
      }
    ),
  judgeExamAttempt: (attemptId: string, config?: ExamJudgeRequest) =>
    request<ExamJudgeResponse>(
      `/api/v1/exams/review/attempts/${encodeURIComponent(attemptId)}/judge`,
      {
        method: "POST",
        body: JSON.stringify(config ?? {})
      }
    ),
  /** Resolves a pack UUID to full detail via catalog listing (no backend UUID route). */
  getTaskPackById: async (taskPackId: string): Promise<TaskPackDetail | null> => {
    const packs = await api.getAllTaskPacks();
    const hit = packs.find((p) => p.id === taskPackId);
    if (!hit) return null;
    return api.getTaskPack(hit.slug);
  }
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

export interface ExamRead {
  id: string;
  title: string;
  description: string;
  task_pack_id: string;
  duration_minutes: number;
  pass_threshold: number;
  max_attempts: number;
  is_published: boolean;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface ExamAttemptStartResponse {
  id: string;
  exam_id: string;
  annotator_id: string;
  started_at: string;
  expires_at: string;
  status: string;
  answers_json: Record<string, unknown>;
  task_times_json: Record<string, unknown>;
  integrity_score: number;
}

export interface ExamAttemptRead {
  id: string;
  exam_id: string;
  annotator_id: string;
  started_at: string;
  expires_at: string;
  submitted_at: string | null;
  status: string;
  score: number | null;
  passed: boolean | null;
  answers_json: Record<string, unknown>;
  task_times_json: Record<string, unknown>;
  integrity_score: number;
  review_notes: string | null;
  released_at: string | null;
  released_by: string | null;
}

export interface IntegrityEventRead {
  id: string;
  attempt_id: string;
  event_type: string;
  severity: string;
  payload_json: Record<string, unknown>;
  created_at: string;
}

export interface ExamAttemptSubmitResponse {
  id: string;
  exam_id: string;
  status: string;
  submitted_at: string | null;
  score: number | null;
  passed: boolean | null;
  integrity_score: number;
}

export interface RubricScoreRow {
  id: string;
  title: string;
  description: string;
  score: number | null;
}

export interface ExamResultRead {
  attempt_id: string;
  exam_id: string;
  status: string;
  score: number | null;
  passed: boolean | null;
  integrity_score: number;
  submitted_at: string | null;
  released_at: string | null;
  review_notes: string | null;
  total_gold_tasks: number | null;
  scored_tasks: number | null;
  rubric?: RubricScoreRow[];
}

export interface ReviewAttemptSummary {
  id: string;
  exam_id: string;
  exam_title: string;
  annotator_id: string;
  annotator_email: string | null;
  started_at: string;
  expires_at: string;
  submitted_at: string | null;
  status: string;
  score: number | null;
  passed: boolean | null;
  integrity_score: number;
  review_notes: string | null;
  released_at: string | null;
  review_rubric_scores?: Record<string, number>;
}

export interface ReviewReleaseRequest {
  release: boolean;
  review_notes?: string | null;
  review_rubric_scores?: Record<string, number> | null;
}

export interface ReviewReleaseResponse {
  id: string;
  exam_id: string;
  status: string;
  released_at: string | null;
  released_by: string | null;
  review_notes: string | null;
  review_rubric_scores?: Record<string, number>;
}

export interface ExamJudgeRequest {
  model?: string | null;
  temperature?: number;
  auto_release?: boolean;
}

export interface ExamJudgeTaskResult {
  task_id: string;
  task_title: string;
  rubric_scores: Record<string, number>;
  reasoning: string;
  confidence: number;
  tokens: number | null;
  latency_ms: number | null;
}

export interface ExamJudgeResponse {
  attempt_id: string;
  rubric_scores: Record<string, number>;
  per_task: ExamJudgeTaskResult[];
  reasoning: string;
  total_tokens: number;
  total_latency_ms: number;
  judge_model: string;
  auto_released: boolean;
}
