/** Extension types for quality, datasets, webhooks, audit, IAA, judge, consensus APIs. */

export interface QualityScoreDetail {
  annotator_id: string;
  trust_score: number;
  gold_accuracy?: number;
  tasks_completed?: number;
  last_updated?: string;
}

export interface QualityLeaderboardEntry {
  rank: number;
  annotator_id: string;
  name?: string;
  trust_score: number;
  tasks_completed: number;
  gold_accuracy: number;
  status: "active" | "calibrating" | "suspended" | string;
}

export interface QualityDashboard {
  overall_trust_score: number;
  active_annotators: number;
  calibration_pass_rate: number;
  avg_gold_accuracy: number;
  timeline?: Array<{ date: string; score: number }>;
}

export interface QualityDriftAlert {
  id: string;
  annotator_id: string;
  annotator_name?: string;
  severity: "warning" | "critical";
  message: string;
  metric_delta: number;
  detected_at: string;
}

export interface CalibrationTest {
  id: string;
  name: string;
  pass_rate: number;
  attempts: number;
  last_run_at?: string;
  status: "active" | "draft" | string;
}

export interface Dataset {
  id: string;
  org_id?: string | null;
  name: string;
  description?: string | null;
  task_type: string;
  tags: unknown[];
  created_by: string;
  created_at: string;
  updated_at: string;
  version_count: number;
}

export interface DatasetVersion {
  id: string;
  dataset_id: string;
  version: number;
  source_pack_ids: string[];
  snapshot_json: Record<string, unknown>;
  stats_json: Record<string, unknown>;
  export_formats: string[];
  created_by: string;
  created_at: string;
  notes?: string | null;
}

export interface DatasetListResponse {
  items: Dataset[];
  total: number;
}

export interface DatasetDetail extends Dataset {
  versions: DatasetVersion[];
}

export interface ExportPayload {
  data: string;
  format: string;
  task_count: number;
  filename: string;
}

export interface WebhookEndpoint {
  id: string;
  url: string;
  events: string[];
  is_active: boolean;
  failure_count: number;
  last_triggered_at: string | null;
  created_at: string;
}

export interface WebhookDelivery {
  id: string;
  endpoint_id: string;
  event: string;
  payload_json: Record<string, unknown>;
  response_status: number | null;
  success: boolean;
  duration_ms: number | null;
  attempts: number;
  created_at: string;
}

export interface AuditLogEntry {
  id: string;
  actor_id: string | null;
  org_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  details_json: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}

export interface AuditLogPage {
  items: AuditLogEntry[];
  total: number;
  skip: number;
  limit: number;
}

export interface AuditLogStats {
  last_24h: Record<string, number>;
  last_7d: Record<string, number>;
  last_30d: Record<string, number>;
}

export interface IAAResult {
  task_pack_id: string;
  n_annotators: number;
  overall_kappa?: number;
  overall_alpha?: number;
  computed_at?: string;
  by_dimension?: Record<string, number>;
  [key: string]: unknown;
}

export interface LLMEvaluation {
  id: string;
  task_pack_id: string;
  task_id: string;
  judge_model: string;
  evaluation_json: Record<string, unknown>;
  confidence: number | null;
  human_override: Record<string, unknown> | null;
  status: "pending" | "accepted" | "rejected" | "overridden" | string;
  created_at: string;
  updated_at: string;
}

export interface JudgeConfig {
  model?: string | null;
  temperature?: number;
  prompt_template?: string | null;
  dimensions?: string[] | null;
}

export interface JudgeResult {
  task_id: string;
  preference: number | null;
  dimensions: Record<string, number> | null;
  reasoning: string;
  confidence: number;
}

export interface JudgeBatchResponse {
  task_pack_id: string;
  results: JudgeResult[];
  judge_model: string;
  total_tokens: number;
  total_latency_ms: number;
}

export interface JudgeEvaluateRequest {
  task_pack_id: string;
  task_ids?: string[] | null;
  config?: JudgeConfig;
}

export interface EvaluationListResponse {
  items: LLMEvaluation[];
  total: number;
  limit: number;
  offset: number;
}

export interface HumanOverrideRequest {
  preference?: number | null;
  dimensions?: Record<string, number> | null;
  reasoning?: string | null;
}

export interface ConsensusTask {
  id: string;
  task_pack_id: string;
  task_id: string;
  status: string;
  n_annotations: number;
  resolved_label?: string | null;
  [key: string]: unknown;
}
