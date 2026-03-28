export type TaskType = "comparison" | "rating" | "ranking";

export interface TaskResponse {
  label: string;
  model?: string;
  text: string;
  seed?: number;
}

export interface TaskDimension {
  name: string;
  description: string;
  scale: number;
}

export interface TaskInference {
  provider: string;
  editable_prompt?: boolean;
  system?: string;
}

export interface TaskItem {
  id: string;
  type: TaskType;
  title: string;
  prompt: string;
  guidelines?: string[];
  inference?: TaskInference;
  responses: TaskResponse[];
  dimensions: TaskDimension[];
}

export interface AnnotationState {
  status: "pending" | "active" | "skipped" | "done";
  preference?: number;
  ranking?: number[];
  dimensions: Record<string, number>;
  justification: string;
  completedAt?: string;
}

export interface WorkspaceSnapshot {
  tasks: TaskItem[];
  annotations: Record<string, AnnotationState>;
  task_times: Record<string, number>;
  active_pack_file: string | null;
}

export interface AuthUser {
  id: string;
  name: string;
  email: string;
  phone?: string | null;
}
