import type {
  CourseModuleRead,
  CourseOverviewResponse,
  CourseProgressResponse,
  CourseSessionRead
} from "@/types/course";

import { request } from "@/lib/api";

async function courseFetch<T>(path: string): Promise<T> {
  return request<T>(`/api/v1/course${path}`);
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
