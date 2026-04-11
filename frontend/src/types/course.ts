export interface CourseSessionBrief {
  id: string;
  number: number;
  title: string;
  duration: string;
}

export interface CourseModuleRead {
  id: string;
  number: number;
  title: string;
  overview_md: string;
  prerequisites: string | null;
  estimated_time: string;
  skills_json: string[];
  bridge_text: string | null;
  session_count: number;
  sessions: CourseSessionBrief[];
}

export interface TaskPackSummary {
  id: string;
  slug: string;
  name: string;
  description: string;
  language: string;
  task_count: number;
  created_at: string;
}

export interface CourseModuleBrief {
  id: string;
  number: number;
  title: string;
  estimated_time: string;
  session_count: number;
}

export interface CourseSessionRead {
  id: string;
  module_id: string;
  number: number;
  title: string;
  overview_md: string;
  rubric_md: string | null;
  questions_md: string | null;
  exercises_md: string | null;
  ai_tasks_md: string | null;
  resources_md: string | null;
  duration: string;
  objectives_json: string[];
  outline_json: Array<{ title: string; items: string[] }>;
  task_packs: TaskPackSummary[];
  module: CourseModuleBrief;
}

export interface SessionProgressItem {
  session_number: number;
  session_title: string;
  completed: boolean;
  packs_total: number;
  packs_completed: number;
}

export interface ModuleProgressItem {
  module_number: number;
  module_title: string;
  sessions: SessionProgressItem[];
  completed_sessions: number;
  total_sessions: number;
}

export interface CourseProgressResponse {
  modules: ModuleProgressItem[];
  total_sessions: number;
  completed_sessions: number;
  current_session: number | null;
}

export interface CourseOverviewResponse {
  modules: CourseModuleRead[];
  total_modules: number;
  total_sessions: number;
}
