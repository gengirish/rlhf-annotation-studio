import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { AnnotationState, AuthUser, TaskItem, WorkspaceSnapshot } from "@/types";

interface AppState {
  user: AuthUser | null;
  token: string | null;
  sessionId: string | null;
  tasks: TaskItem[];
  annotations: Record<string, AnnotationState>;
  taskTimes: Record<string, number>;
  activePackFile: string | null;
  currentTaskIndex: number;
  setAuth: (payload: { user: AuthUser; token: string; sessionId: string }) => void;
  logout: () => void;
  loadTasks: (tasks: TaskItem[], activePackFile: string | null) => void;
  setCurrentTaskIndex: (idx: number) => void;
  updateAnnotation: (taskId: string, patch: Partial<AnnotationState>) => void;
  setTaskTime: (taskId: string, value: number) => void;
  hydrateWorkspace: (workspace: WorkspaceSnapshot) => void;
}

const defaultAnnotation = (): AnnotationState => ({
  status: "pending",
  dimensions: {},
  justification: ""
});

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      sessionId: null,
      tasks: [],
      annotations: {},
      taskTimes: {},
      activePackFile: null,
      currentTaskIndex: 0,

      setAuth: ({ user, token, sessionId }) => {
        localStorage.setItem("rlhf_authToken", token);
        set({ user, token, sessionId });
      },

      logout: () => {
        localStorage.removeItem("rlhf_authToken");
        set({
          user: null,
          token: null,
          sessionId: null,
          tasks: [],
          annotations: {},
          taskTimes: {},
          activePackFile: null,
          currentTaskIndex: 0
        });
      },

      loadTasks: (tasks, activePackFile) => {
        const existing = get().annotations;
        const merged: Record<string, AnnotationState> = {};
        tasks.forEach((task, index) => {
          merged[task.id] = existing[task.id] || {
            ...defaultAnnotation(),
            status: index === 0 ? "active" : "pending"
          };
        });
        set({ tasks, annotations: merged, activePackFile, currentTaskIndex: 0 });
      },

      setCurrentTaskIndex: (idx) => set({ currentTaskIndex: idx }),

      updateAnnotation: (taskId, patch) => {
        const curr = get().annotations[taskId] || defaultAnnotation();
        set({
          annotations: {
            ...get().annotations,
            [taskId]: {
              ...curr,
              ...patch
            }
          }
        });
      },

      setTaskTime: (taskId, value) => {
        set({ taskTimes: { ...get().taskTimes, [taskId]: value } });
      },

      hydrateWorkspace: (workspace) => {
        set({
          tasks: workspace.tasks || [],
          annotations: workspace.annotations || {},
          taskTimes: workspace.task_times || {},
          activePackFile: workspace.active_pack_file || null,
          currentTaskIndex: 0
        });
      }
    }),
    { name: "rlhf-next-store" }
  )
);
