import type {
  CourseModuleRead,
  CourseOverviewResponse,
  CourseProgressResponse,
  CourseSessionRead
} from "@/types/course";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("rlhf_authToken");
}

async function courseFetch<T>(path: string): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}/api/v1/course${path}`, { headers });
  if (!res.ok) throw new Error(`Course API error: ${res.status}`);
  return res.json() as Promise<T>;
}

export const courseApi = {
  getOverview: () => courseFetch<CourseOverviewResponse>("/overview"),
  getModules: () => courseFetch<CourseModuleRead[]>("/modules"),
  getModule: (num: number) => courseFetch<CourseModuleRead>(`/modules/${num}`),
  getSession: (num: number) => courseFetch<CourseSessionRead>(`/sessions/${num}`),
  getSessionRubric: (num: number) => courseFetch<{ rubric_md: string | null }>(`/sessions/${num}/rubric`),
  getSessionQuestions: (num: number) =>
    courseFetch<{ questions_md: string | null }>(`/sessions/${num}/questions`),
  getSessionResources: (num: number) =>
    courseFetch<{ resources_md: string | null }>(`/sessions/${num}/resources`),
  getProgress: () => courseFetch<CourseProgressResponse>("/progress")
};
