import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createMockTransport } from "./handlers";
import { createApiClient } from "../api/client";

let mock: ReturnType<typeof createMockTransport>;
let client: ReturnType<typeof createApiClient>;
beforeEach(() => {
  mock = createMockTransport({
    latencyMs: 0,
    searchLatencyMs: 0,
    processingMs: 20,
  });
  client = createApiClient({ mode: "mock", mockTransport: mock.handler });
});
afterEach(() => mock.reset());
const login = (role = "manager") =>
  client.login(`${role}@enterprise.local`, "demo123");

describe("mock API contract", () => {
  it("returns the backend login shape, including expires_in and no UI-only user fields", async () => {
    const response = await mock.handler("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({
        username: "manager@enterprise.local",
        password: "demo123",
      }),
    });
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(Object.keys(body).sort()).toEqual([
      "access_token",
      "expires_in",
      "token_type",
      "user",
    ]);
    expect(Object.keys(body.user).sort()).toEqual([
      "clearance",
      "department",
      "role",
      "user_id",
      "username",
    ]);
  });
  it("rejects unauthenticated, expired, and revoked sessions", async () => {
    await expect(client.search("leave", "missing")).rejects.toMatchObject({
      status: 401,
    });
    const session = await login();
    vi.spyOn(Date, "now").mockReturnValue(Date.now() + 3600_001);
    await expect(
      client.search("leave", session.access_token),
    ).rejects.toMatchObject({ status: 401 });
    vi.restoreAllMocks();
    await client.logout(session.access_token);
    await expect(
      client.search("leave", session.access_token),
    ).rejects.toMatchObject({ status: 401 });
  });
  it("enforces upload permission and department/clearance visibility", async () => {
    const staff = await login("staff");
    await expect(
      client.upload(new File(["pdf"], "policy.pdf"), staff.access_token),
    ).rejects.toMatchObject({ status: 403 });
    expect((await client.documents(staff.access_token)).documents).toHaveLength(
      3,
    );
    expect(
      (
        await client.search(
          "manager reviews and leadership strategy",
          staff.access_token,
        )
      ).results,
    ).toEqual([]);
    await expect(
      client.document("doc-strategy", staff.access_token),
    ).rejects.toMatchObject({ status: 404 });
    const executive = await login("executive");
    expect(
      (await client.documents(executive.access_token)).documents,
    ).toHaveLength(5);
    expect(
      (await client.search("leadership strategy", executive.access_token))
        .results[0].document_id,
    ).toBe("doc-strategy");
  });
  it("matches the architecture search structure and respects limits and filters", async () => {
    const { access_token } = await login("executive");
    const response = await client.search(
      "leave and remote work",
      access_token,
      { top_k: 1, search_mode: "keyword", filters: { department: "Global" } },
    );
    expect(response).toMatchObject({
      query: "leave and remote work",
      search_mode: "keyword",
      total: 1,
      request_id: expect.any(String),
    });
    expect(response.results[0]).toEqual({
      document_id: "doc-handbook",
      chunk_id: "doc-handbook-chunk-1",
      title: "Employee_Handbook.pdf",
      content: expect.any(String),
      score: 0.92,
      content_type: "application/pdf",
      department_id: "Global",
      clearance_level: 1,
      citation: { page: 12, line_start: null, line_end: null },
    });
    expect(response).not.toHaveProperty("answer");
    expect(
      (
        await client.search("leave", access_token, {
          filters: { department: "HR" },
        })
      ).results,
    ).toEqual([]);
  });
  it.each([0, 21, 1.5])(
    "validates top_k %s with FastAPI-style 422 errors",
    async (top_k) => {
      const { access_token } = await login();
      await expect(
        client.search("leave", access_token, { top_k }),
      ).rejects.toMatchObject({
        status: 422,
        message: expect.stringContaining("top_k"),
      });
    },
  );
  it("validates missing query, malformed JSON, and unsupported search modes", async () => {
    const { access_token } = await login();
    await expect(client.search("", access_token)).rejects.toMatchObject({
      status: 422,
    });
    const response = await mock.handler("/api/v1/search", {
      method: "POST",
      headers: { Authorization: `Bearer ${access_token}` },
      body: "bad json",
    });
    expect(response.status).toBe(422);
    await expect(
      client.search("leave", access_token, {
        search_mode: "invalid" as "hybrid",
      }),
    ).rejects.toMatchObject({ status: 422 });
  });
  it("returns the complete 202 upload response and transitions processing to ready", async () => {
    vi.useFakeTimers();
    const { access_token } = await login();
    const body = new FormData();
    body.append(
      "file",
      new File(["pdf"], "policy.pdf", { type: "application/pdf" }),
    );
    const response = await mock.handler("/api/v1/upload", {
      method: "POST",
      headers: { Authorization: `Bearer ${access_token}` },
      body,
    });
    expect(response.status).toBe(202);
    const uploaded = await response.json();
    expect(uploaded).toEqual({
      document_id: expect.any(String),
      filename: "policy.pdf",
      content_type: "application/pdf",
      size_bytes: 3,
      status: "queued",
      message: "Document queued for General with clearance 2",
    });
    expect(
      (await client.document(uploaded.document_id, access_token)).status,
    ).toBe("processing");
    await vi.advanceTimersByTimeAsync(20);
    expect(
      (await client.document(uploaded.document_id, access_token)).status,
    ).toBe("ready");
  });
  it("supports processing failure and text previews", async () => {
    const { access_token } = await login();
    const uploaded = await client.upload(
      new File(["# Test policy"], "processing-error.md"),
      access_token,
    );
    expect(
      (await client.document(uploaded.document_id, access_token)).preview,
    ).toBe("# Test policy");
    await new Promise((resolve) => setTimeout(resolve, 30));
    expect(
      (await client.document(uploaded.document_id, access_token)).status,
    ).toBe("failed");
  });
  it("rejects unsupported and empty files and a missing multipart file", async () => {
    const { access_token } = await login();
    await expect(
      client.upload(new File(["data"], "data.exe"), access_token),
    ).rejects.toMatchObject({ status: 400 });
    await expect(
      client.upload(new File([], "empty.txt"), access_token),
    ).rejects.toMatchObject({ status: 400 });
    const response = await mock.handler("/api/v1/upload", {
      method: "POST",
      headers: { Authorization: `Bearer ${access_token}` },
      body: new FormData(),
    });
    expect(response.status).toBe(422);
  });
  it("provides deterministic failures/empty results and resets state", async () => {
    const { access_token } = await login();
    mock.next("/api/v1/search", "server-error");
    await expect(client.search("leave", access_token)).rejects.toMatchObject({
      status: 503,
    });
    mock.next("/api/v1/search", "offline");
    await expect(client.search("leave", access_token)).rejects.toMatchObject({
      status: 0,
    });
    mock.next("/api/v1/search", "empty");
    expect((await client.search("leave", access_token)).results).toEqual([]);
    expect((await client.search("leave", access_token)).results).toHaveLength(
      1,
    );
    await client.upload(new File(["pdf"], "new.pdf"), access_token);
    mock.reset();
    const session = await login();
    expect(
      (await client.documents(session.access_token)).documents,
    ).toHaveLength(4);
  });
});
