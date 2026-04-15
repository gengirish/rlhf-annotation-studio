import { describe, it, expect, beforeEach, vi } from "vitest";
import { api, ApiError } from "@/lib/api";

const mockFetch = vi.fn();
globalThis.fetch = mockFetch as typeof fetch;

function jsonResponse(data: unknown, status = 200) {
  const body = JSON.stringify(data);
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(body)
  } as Response);
}

function errorResponse(status: number, detail?: string) {
  return Promise.resolve({
    ok: false,
    status,
    json: () => Promise.resolve(detail ? { detail } : {}),
    text: () => Promise.resolve(JSON.stringify(detail ? { detail } : {}))
  } as Response);
}

describe("API client", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    localStorage.clear();
  });

  describe("request internals", () => {
    it("includes Authorization header when token exists in localStorage", async () => {
      localStorage.setItem("rlhf_authToken", "test-jwt-token");
      mockFetch.mockReturnValueOnce(jsonResponse({ status: "ok" }));
      await api.health();
      const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
      const headers = init.headers as Record<string, string>;
      expect(headers.Authorization).toBe("Bearer test-jwt-token");
    });

    it("omits Authorization header when no token", async () => {
      mockFetch.mockReturnValueOnce(jsonResponse({ status: "ok" }));
      await api.health();
      const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
      const headers = init.headers as Record<string, string>;
      expect(headers.Authorization).toBeUndefined();
    });

    it("throws ApiError on non-2xx response", async () => {
      mockFetch.mockReturnValueOnce(errorResponse(401, "Unauthorized"));
      await expect(api.health()).rejects.toThrow(ApiError);
    });

    it("ApiError contains status and message", async () => {
      mockFetch.mockReturnValueOnce(errorResponse(403, "Forbidden"));
      const err = await api.health().catch((e: unknown) => e);
      expect(err).toBeInstanceOf(ApiError);
      expect((err as ApiError).status).toBe(403);
      expect((err as ApiError).message).toBe("Forbidden");
    });

    it("sends Content-Type application/json", async () => {
      mockFetch.mockReturnValueOnce(jsonResponse({ status: "ok" }));
      await api.health();
      const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
      const headers = init.headers as Record<string, string>;
      expect(headers["Content-Type"]).toBe("application/json");
    });
  });

  describe("register", () => {
    it("sends correct payload", async () => {
      const authResp = {
        token: "jwt",
        annotator: { id: "1", name: "A", email: "a@b.com" },
        session_id: "s1"
      };
      mockFetch.mockReturnValueOnce(jsonResponse(authResp, 201));
      const result = await api.register({
        name: "A",
        email: "a@b.com",
        password: "secret"
      });
      const [url, init] = mockFetch.mock.calls[0] as [string, RequestInit];
      expect(url).toContain("/api/v1/auth/register");
      expect(init.method).toBe("POST");
      const body = JSON.parse(init.body as string);
      expect(body.name).toBe("A");
      expect(body.email).toBe("a@b.com");
      expect(body.password).toBe("secret");
      expect(result.token).toBe("jwt");
    });
  });

  describe("login", () => {
    it("sends correct payload", async () => {
      const authResp = {
        token: "jwt2",
        annotator: { id: "2", name: "B", email: "b@c.com" },
        session_id: "s2"
      };
      mockFetch.mockReturnValueOnce(jsonResponse(authResp));
      const result = await api.login({ email: "b@c.com", password: "pass" });
      const [url, init] = mockFetch.mock.calls[0] as [string, RequestInit];
      expect(url).toContain("/api/v1/auth/login");
      expect(init.method).toBe("POST");
      expect(result.token).toBe("jwt2");
    });
  });

  describe("workspace", () => {
    it("putWorkspace sends WorkspaceSnapshot", async () => {
      mockFetch.mockReturnValueOnce(jsonResponse({ ok: true }));
      await api.putWorkspace("session-1", {
        tasks: [],
        annotations: {},
        task_times: {},
        active_pack_file: null
      });
      const [url, init] = mockFetch.mock.calls[0] as [string, RequestInit];
      expect(url).toContain("/api/v1/sessions/session-1/workspace");
      expect(init.method).toBe("PUT");
      const body = JSON.parse(init.body as string);
      expect(body).toHaveProperty("tasks");
      expect(body).toHaveProperty("annotations");
    });

    it("getWorkspace calls correct URL", async () => {
      mockFetch.mockReturnValueOnce(
        jsonResponse({
          session_id: "s1",
          annotator_id: "a1",
          tasks: [],
          annotations: {},
          task_times: {},
          active_pack_file: null
        })
      );
      await api.getWorkspace("session-1");
      const [url] = mockFetch.mock.calls[0] as [string, RequestInit];
      expect(url).toContain("/api/v1/sessions/session-1/workspace");
    });
  });

  describe("task packs", () => {
    it("getTaskPacks calls correct URL", async () => {
      mockFetch.mockReturnValueOnce(jsonResponse({ packs: [] }));
      const result = await api.getTaskPacks();
      expect(mockFetch.mock.calls[0][0] as string).toContain("/api/v1/tasks/packs");
      expect(result.packs).toEqual([]);
    });

    it("getTaskPack encodes slug", async () => {
      mockFetch.mockReturnValueOnce(
        jsonResponse({
          id: "1",
          slug: "my-pack",
          name: "Pack",
          description: "",
          language: "en",
          task_count: 0,
          created_at: "",
          tasks_json: []
        })
      );
      await api.getTaskPack("my-pack");
      expect(mockFetch.mock.calls[0][0] as string).toContain(
        "/api/v1/tasks/packs/my-pack"
      );
    });

    it("validateTasks sends tasks with strict_mode false", async () => {
      mockFetch.mockReturnValueOnce(jsonResponse({ ok: true, issues: [] }));
      await api.validateTasks([]);
      const init = mockFetch.mock.calls[0][1] as RequestInit;
      const body = JSON.parse(init.body as string);
      expect(body.tasks).toEqual([]);
      expect(body.strict_mode).toBe(false);
    });
  });
});
