import { useEffect, useState } from "react";
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
  getFirstUnfinishedTaskIndex: () => number;
  getNextUnfinishedTaskIndex: (fromIdx: number) => number | null;
  updateAnnotation: (taskId: string, patch: Partial<AnnotationState>) => void;
  setTaskTime: (taskId: string, value: number) => void;
  hydrateWorkspace: (workspace: WorkspaceSnapshot) => void;
}

const defaultAnnotation = (): AnnotationState => ({
  status: "pending",
  dimensions: {},
  justification: ""
});

function firstUnfinishedIndex(tasks: TaskItem[], annotations: Record<string, AnnotationState>): number {
  if (!tasks.length) return 0;
  const idx = tasks.findIndex((task) => annotations[task.id]?.status !== "done");
  return idx >= 0 ? idx : 0;
}

function nextUnfinishedIndex(
  tasks: TaskItem[],
  annotations: Record<string, AnnotationState>,
  fromIdx: number
): number | null {
  for (let i = fromIdx + 1; i < tasks.length; i += 1) {
    if (annotations[tasks[i].id]?.status !== "done") return i;
  }
  return null;
}

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
        const prev = get();
        const sessionChanged = prev.sessionId !== sessionId;
        set({
          user,
          token,
          sessionId,
          ...(sessionChanged
            ? { tasks: [], annotations: {}, taskTimes: {}, activePackFile: null, currentTaskIndex: 0 }
            : {}),
        });
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
        const prev = get();
        const packChanged = prev.activePackFile !== activePackFile;
        const baseAnnotations = packChanged ? {} : prev.annotations;
        const merged: Record<string, AnnotationState> = {};
        tasks.forEach((task, index) => {
          merged[task.id] = baseAnnotations[task.id] || {
            ...defaultAnnotation(),
            status: index === 0 ? "active" : "pending"
          };
        });
        const startIndex = firstUnfinishedIndex(tasks, merged);
        set({
          tasks,
          annotations: merged,
          taskTimes: packChanged ? {} : prev.taskTimes,
          activePackFile,
          currentTaskIndex: startIndex,
        });
      },

      setCurrentTaskIndex: (idx) => set({ currentTaskIndex: idx }),

      getFirstUnfinishedTaskIndex: () => {
        const state = get();
        return firstUnfinishedIndex(state.tasks, state.annotations);
      },

      getNextUnfinishedTaskIndex: (fromIdx) => {
        const state = get();
        return nextUnfinishedIndex(state.tasks, state.annotations, fromIdx);
      },

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
        const tasks = workspace.tasks || [];
        const annotations = workspace.annotations || {};
        set({
          tasks,
          annotations,
          taskTimes: workspace.task_times || {},
          activePackFile: workspace.active_pack_file || null,
          currentTaskIndex: firstUnfinishedIndex(tasks, annotations)
        });
      }
    }),
    {
      name: "rlhf-next-store",
      onRehydrateStorage: () => () => {
        useAppStore.setState({ _hydrated: true } as Partial<AppState>);
      }
    }
  )
);

export function useHasHydrated() {
  const [hydrated, setHydrated] = useState(false);
  useEffect(() => {
    const unsub = useAppStore.persist.onFinishHydration(() => setHydrated(true));
    if (useAppStore.persist.hasHydrated()) setHydrated(true);
    return unsub;
  }, []);
  return hydrated;
}
