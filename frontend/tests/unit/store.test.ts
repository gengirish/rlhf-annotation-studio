import { beforeEach, describe, expect, it } from "vitest";

import { useAppStore } from "@/lib/state/store";
import type { AnnotationState, AuthUser, TaskItem, WorkspaceSnapshot } from "@/types";

const mockUser: AuthUser = {
  id: "user-1",
  name: "Test User",
  email: "test@example.com",
  role: "annotator",
  org_id: null,
};

const mockTasks: TaskItem[] = [
  {
    id: "task-1",
    type: "comparison",
    title: "Task 1",
    prompt: "Compare these",
    responses: [
      { label: "A", text: "Response A" },
      { label: "B", text: "Response B" },
    ],
    dimensions: [{ name: "Accuracy", description: "How accurate", scale: 5 }],
  },
  {
    id: "task-2",
    type: "rating",
    title: "Task 2",
    prompt: "Rate this",
    responses: [{ label: "Response", text: "Some text" }],
    dimensions: [{ name: "Quality", description: "Overall quality", scale: 5 }],
  },
];

describe("useAppStore", () => {
  beforeEach(() => {
    localStorage.clear();
    useAppStore.setState({
      user: null,
      token: null,
      sessionId: null,
      tasks: [],
      annotations: {},
      taskTimes: {},
      activePackFile: null,
      currentTaskIndex: 0,
    });
  });

  describe("setAuth", () => {
    it("populates user, token, and sessionId", () => {
      useAppStore.getState().setAuth({
        user: mockUser,
        token: "jwt-token",
        sessionId: "sess-1",
      });

      const s = useAppStore.getState();
      expect(s.user).toEqual(mockUser);
      expect(s.token).toBe("jwt-token");
      expect(s.sessionId).toBe("sess-1");
    });

    it("stores rlhf_authToken in localStorage", () => {
      useAppStore.getState().setAuth({
        user: mockUser,
        token: "secret-token",
        sessionId: "sess-1",
      });

      expect(localStorage.getItem("rlhf_authToken")).toBe("secret-token");
    });
  });

  describe("logout", () => {
    it("clears all state fields", () => {
      useAppStore.getState().setAuth({
        user: mockUser,
        token: "t",
        sessionId: "s",
      });
      useAppStore.getState().loadTasks(mockTasks, "pack.json");
      useAppStore.getState().setTaskTime("task-1", 42);
      useAppStore.getState().setCurrentTaskIndex(1);

      useAppStore.getState().logout();

      const s = useAppStore.getState();
      expect(s.user).toBeNull();
      expect(s.token).toBeNull();
      expect(s.sessionId).toBeNull();
      expect(s.tasks).toEqual([]);
      expect(s.annotations).toEqual({});
      expect(s.taskTimes).toEqual({});
      expect(s.activePackFile).toBeNull();
      expect(s.currentTaskIndex).toBe(0);
    });

    it("removes rlhf_authToken from localStorage", () => {
      useAppStore.getState().setAuth({
        user: mockUser,
        token: "to-remove",
        sessionId: "s",
      });
      expect(localStorage.getItem("rlhf_authToken")).toBe("to-remove");

      useAppStore.getState().logout();

      expect(localStorage.getItem("rlhf_authToken")).toBeNull();
    });
  });

  describe("loadTasks", () => {
    it("sets tasks and creates annotation entries", () => {
      useAppStore.getState().loadTasks(mockTasks, "tasks/pack.json");

      const s = useAppStore.getState();
      expect(s.tasks).toEqual(mockTasks);
      expect(s.activePackFile).toBe("tasks/pack.json");
      expect(Object.keys(s.annotations)).toEqual(["task-1", "task-2"]);
      expect(s.annotations["task-1"]).toMatchObject({
        status: "active",
        dimensions: {},
        justification: "",
      });
      expect(s.annotations["task-2"]).toMatchObject({
        status: "pending",
        dimensions: {},
        justification: "",
      });
    });

    it("sets first task to active, rest to pending", () => {
      useAppStore.getState().loadTasks(mockTasks, null);

      const { annotations } = useAppStore.getState();
      expect(annotations["task-1"]?.status).toBe("active");
      expect(annotations["task-2"]?.status).toBe("pending");
    });

    it("resets currentTaskIndex to 0", () => {
      useAppStore.getState().setCurrentTaskIndex(5);
      useAppStore.getState().loadTasks(mockTasks, "x.json");

      expect(useAppStore.getState().currentTaskIndex).toBe(0);
    });

    it("preserves existing annotations for matching task IDs", () => {
      const preserved: AnnotationState = {
        status: "done",
        dimensions: { Accuracy: 4 },
        justification: "kept",
        preference: 1,
      };
      useAppStore.setState({
        annotations: { "task-1": preserved },
      });

      useAppStore.getState().loadTasks(mockTasks, "pack.json");

      const { annotations } = useAppStore.getState();
      expect(annotations["task-1"]).toEqual(preserved);
      expect(annotations["task-2"]).toMatchObject({
        status: "pending",
        dimensions: {},
        justification: "",
      });
    });
  });

  describe("updateAnnotation", () => {
    it("shallow-merges into existing annotation", () => {
      useAppStore.getState().loadTasks(mockTasks, null);
      useAppStore.getState().updateAnnotation("task-1", {
        status: "done",
        justification: "merged",
      });

      const ann = useAppStore.getState().annotations["task-1"];
      expect(ann?.status).toBe("done");
      expect(ann?.justification).toBe("merged");
      expect(ann?.dimensions).toEqual({});
    });

    it("creates default annotation if none exists", () => {
      useAppStore.getState().updateAnnotation("unknown-id", { status: "skipped" });

      const ann = useAppStore.getState().annotations["unknown-id"];
      expect(ann).toMatchObject({
        status: "skipped",
        dimensions: {},
        justification: "",
      });
    });
  });

  describe("setTaskTime", () => {
    it("sets time for specific task", () => {
      useAppStore.getState().setTaskTime("task-1", 120);
      useAppStore.getState().setTaskTime("task-2", 30);

      expect(useAppStore.getState().taskTimes).toEqual({
        "task-1": 120,
        "task-2": 30,
      });
    });
  });

  describe("hydrateWorkspace", () => {
    it("replaces all workspace fields", () => {
      const workspace: WorkspaceSnapshot = {
        tasks: [mockTasks[0]!],
        annotations: {
          "task-1": {
            status: "done",
            dimensions: {},
            justification: "ok",
          },
        },
        task_times: { "task-1": 99 },
        active_pack_file: "remote.json",
      };

      useAppStore.getState().loadTasks(mockTasks, "old.json");
      useAppStore.getState().hydrateWorkspace(workspace);

      const s = useAppStore.getState();
      expect(s.tasks).toEqual([mockTasks[0]!]);
      expect(s.annotations).toEqual(workspace.annotations);
      expect(s.taskTimes).toEqual({ "task-1": 99 });
      expect(s.activePackFile).toBe("remote.json");
    });

    it("resets currentTaskIndex to 0", () => {
      useAppStore.getState().setCurrentTaskIndex(3);
      useAppStore.getState().hydrateWorkspace({
        tasks: [],
        annotations: {},
        task_times: {},
        active_pack_file: null,
      });

      expect(useAppStore.getState().currentTaskIndex).toBe(0);
    });
  });

  describe("setCurrentTaskIndex", () => {
    it("updates the current task index", () => {
      expect(useAppStore.getState().currentTaskIndex).toBe(0);
      useAppStore.getState().setCurrentTaskIndex(7);
      expect(useAppStore.getState().currentTaskIndex).toBe(7);
    });
  });
});
