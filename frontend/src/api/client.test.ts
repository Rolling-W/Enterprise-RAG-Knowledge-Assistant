import { describe, expect, it, vi } from "vitest";
import { createApiClient } from "./client";
import {
  citationLocation,
  toAssistantResponse,
  toMessages,
  toSession,
} from "./adapters";
import { searchFixture, tokenFixture, uploadFixture } from "../test/fixtures";

const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status });
describe("HTTP client and display adapters", () => {
  it("honors server permissions, including an explicitly empty permission set", () => {
    expect(
      toSession({
        ...tokenFixture,
        user: {
          user_id: "a",
          username: "admin",
          role: "admin",
          permissions: [],
          department: "Executive",
          clearance: 3,
        },
      }).user.permissions,
    ).toEqual([]);
  });
  it("serializes Sprint 4 document queries and management requests without client role claims", async () => {
    const transport = vi.fn().mockImplementation(async () => response({}));
    const client = createApiClient({
      mode: "live",
      baseUrl: "http://backend.test",
      fetchTransport: transport,
    });
    await client.documents("token", {
      page: 2,
      page_size: 10,
      q: "policy & benefits",
      permission_level: 2,
      creator_id: "a/b",
      status: "indexed",
      sort_by: "filename",
      sort_order: "asc",
    });
    const url = new URL(transport.mock.calls[0][0]);
    expect(url.searchParams.get("q")).toBe("policy & benefits");
    expect(url.searchParams.get("page")).toBe("2");
    expect(url.searchParams.get("permission_level")).toBe("2");
    await client.changePermission("doc/a", 3, "token");
    expect(transport.mock.calls[1][0]).toBe(
      "http://backend.test/api/v1/documents/doc%2Fa/permissions",
    );
    expect(JSON.parse(transport.mock.calls[1][1].body)).toEqual({
      permission_level: 3,
    });
    await client.upload(new File(["policy"], "policy.txt"), "token", 2);
    expect(
      (transport.mock.calls[2][1].body as FormData).get("permission_level"),
    ).toBe("2");
    transport.mockResolvedValueOnce(new Response(null, { status: 204 }));
    await expect(
      client.deleteDocument("doc/a", "token"),
    ).resolves.toBeUndefined();
    expect(transport.mock.calls[3][1].method).toBe("DELETE");
    await client.reindexDocument("doc/a", "token");
    expect(transport.mock.calls[4][0]).toContain("/doc%2Fa/reindex");
  });
  it("uses owner-scoped conversation routes and submits user content only", async () => {
    const transport = vi.fn().mockImplementation(async () => response({}));
    const client = createApiClient({ mode: "live", fetchTransport: transport });
    await client.createConversation("token", "Benefits");
    await client.sendMessage("conv/a", "annual leave", "token");
    expect(JSON.parse(transport.mock.calls[1][1].body)).toEqual({
      content: "annual leave",
    });
    expect(transport.mock.calls[1][0]).toContain("/conv%2Fa/messages");
    await client.conversation("conv/a", "token");
    await client.conversations("token", 2);
    expect(transport.mock.calls[3][0]).toContain("?page=2&page_size=20");
    transport.mockResolvedValueOnce(new Response(null, { status: 204 }));
    await expect(
      client.deleteConversation("conv/a", "token"),
    ).resolves.toBeUndefined();
    await client.debugSearch(
      { query: "leave", search_mode: "hybrid", top_k: 3, candidate_limit: 30 },
      "token",
    );
    expect(JSON.parse(transport.mock.calls[5][1].body)).toEqual({
      query: "leave",
      search_mode: "hybrid",
      top_k: 3,
      candidate_limit: 30,
    });
    for (const [, init] of transport.mock.calls)
      expect(new Headers(init.headers).get("Authorization")).toBe(
        "Bearer token",
      );
  });
  it("restores sequence order and coordinates without inventing missing scores or snippets", () => {
    const restored = toMessages([
      {
        message_id: "m2",
        sequence: 2,
        role: "assistant",
        content: "Answer",
        created_at: "2026-11-01T10:00:00Z",
        citations: [
          {
            document_id: "d",
            chunk_id: "c",
            title: "Private title",
            permission_level: 2,
            page: 12,
            line_start: null,
            line_end: null,
            unavailable: true,
          },
        ],
      },
      {
        message_id: "m1",
        sequence: 1,
        role: "user",
        content: "Question",
        created_at: "2026-11-01T10:00:00Z",
        citations: [],
      },
    ]);
    expect(restored.map((item) => item.id)).toEqual(["m1", "m2"]);
    expect(restored[1].citations?.[0]).toMatchObject({
      title: "Unavailable source",
      page: 12,
      content: "",
      unavailable: true,
    });
    expect(restored[1].citations?.[0].score).toBeUndefined();
  });
  it("uses the configured live URL and JSON headers, adapts a backend login without UI fields", async () => {
    const transport = vi.fn().mockResolvedValue(response(tokenFixture));
    const client = createApiClient({
      mode: "live",
      baseUrl: "http://backend.test/",
      fetchTransport: transport,
    });
    const session = await client.login("manager@enterprise.local", "password");
    expect(transport).toHaveBeenCalledWith(
      "http://backend.test/api/v1/auth/login",
      expect.objectContaining({ method: "POST" }),
    );
    const init = transport.mock.calls[0][1] as RequestInit;
    expect(new Headers(init.headers).get("Content-Type")).toBe(
      "application/json",
    );
    expect(JSON.parse(init.body as string)).toEqual({
      username: "manager@enterprise.local",
      password: "password",
    });
    expect(session.user.name).toBe("manager");
    expect(session.user.permissions).toContain("document:upload");
    expect(session.expires_in).toBe(3600);
  });
  it("attaches bearer credentials and preserves the new search DTO", async () => {
    const transport = vi.fn().mockResolvedValue(response(searchFixture));
    const client = createApiClient({ mode: "live", fetchTransport: transport });
    expect(await client.search("employee benefits", "signed-token")).toEqual(
      searchFixture,
    );
    const init = transport.mock.calls[0][1] as RequestInit;
    expect(new Headers(init.headers).get("Authorization")).toBe(
      "Bearer signed-token",
    );
    expect(JSON.parse(init.body as string)).toEqual({
      query: "employee benefits",
      search_mode: "hybrid",
      top_k: 5,
    });
    const display = toAssistantResponse(searchFixture);
    expect(display.answer).toBe(searchFixture.results[0].content);
    expect(display.citations[0]).toMatchObject({
      id: "chunk_001",
      score: 0.92,
      document_id: "doc_001",
      page: 12,
      line_start: 45,
      line_end: 49,
    });
    expect(citationLocation(display.citations[0])).toBe(
      "Page 12 · Lines 45–49",
    );
  });
  it("normalizes Markdown MIME without manually setting a multipart boundary", async () => {
    const transport = vi.fn().mockResolvedValue(response(uploadFixture, 202));
    const client = createApiClient({ mode: "live", fetchTransport: transport });
    await client.upload(
      new File(["policy"], "policy.md", { type: "text/plain" }),
      "token",
    );
    const init = transport.mock.calls[0][1] as RequestInit;
    const file = (init.body as FormData).get("file") as File;
    expect(file.type).toBe("text/markdown");
    expect(file.name).toBe("policy.md");
    expect(file.size).toBe(6);
    expect(new Headers(init.headers).has("Content-Type")).toBe(false);
  });
  it("renders FastAPI validation errors as readable messages", async () => {
    const client = createApiClient({
      mode: "live",
      fetchTransport: async () =>
        response(
          { detail: [{ loc: ["body", "query"], msg: "Field required" }] },
          422,
        ),
    });
    await expect(client.search("", "token")).rejects.toMatchObject({
      status: 422,
      message: "query: Field required",
    });
  });
  it("handles non-JSON server failures and connection failures", async () => {
    const unavailable = createApiClient({
      mode: "live",
      fetchTransport: async () => new Response("Bad gateway", { status: 502 }),
    });
    await expect(unavailable.search("leave", "token")).rejects.toMatchObject({
      status: 502,
      message: expect.stringContaining("unavailable"),
    });
    const offline = createApiClient({
      mode: "live",
      fetchTransport: async () => {
        throw new TypeError("offline");
      },
    });
    await expect(offline.search("leave", "token")).rejects.toMatchObject({
      status: 0,
      message: expect.stringContaining("connect"),
    });
  });
  it("calls document endpoints in live mode and never substitutes mock data on failure", async () => {
    const transport = vi
      .fn()
      .mockResolvedValue(response({ detail: "Not Found" }, 404));
    const mock = vi.fn();
    const client = createApiClient({
      mode: "live",
      fetchTransport: transport,
      mockTransport: mock,
    });
    await expect(client.documents("token")).rejects.toMatchObject({
      status: 404,
    });
    await expect(client.document("doc", "token")).rejects.toMatchObject({
      status: 404,
    });
    await client.logout("token");
    expect(transport).toHaveBeenCalledTimes(2);
    expect(mock).not.toHaveBeenCalled();
  });
  it("supports empty retrieval and unavailable source locations", () => {
    const empty = toAssistantResponse({
      ...searchFixture,
      total: 0,
      results: [],
    });
    expect(empty.citations).toEqual([]);
    expect(empty.answer).toContain("couldn’t find");
    const result = toAssistantResponse({
      ...searchFixture,
      results: [
        {
          ...searchFixture.results[0],
          citation: { page: null, line_start: null, line_end: null },
        },
      ],
    });
    expect(citationLocation(result.citations[0])).toBe("Source excerpt");
  });

  it.each([true, false])(
    "notifies on protected 401, including JSON=%s",
    async (json) => {
      const client = createApiClient({
        mode: "live",
        fetchTransport: async () =>
          json
            ? response({ detail: "Expired token" }, 401)
            : new Response("Unauthorized", { status: 401 }),
      });
      const listener = vi.fn();
      const unsubscribe = client.onUnauthorized(listener);
      await expect(
        client.search("leave", "expired-token"),
      ).rejects.toMatchObject({ status: 401 });
      expect(listener).toHaveBeenCalledWith("expired-token");
      unsubscribe();
      await expect(
        client.search("leave", "expired-token"),
      ).rejects.toMatchObject({ status: 401 });
      expect(listener).toHaveBeenCalledTimes(1);
    },
  );

  it("keeps login errors and forbidden requests out of session invalidation", async () => {
    const transport = vi
      .fn()
      .mockResolvedValueOnce(response({ detail: "Invalid credentials" }, 401))
      .mockResolvedValueOnce(response({ detail: "Permission required" }, 403));
    const client = createApiClient({ mode: "live", fetchTransport: transport });
    const listener = vi.fn();
    client.onUnauthorized(listener);
    await expect(client.login("manager", "wrong")).rejects.toMatchObject({
      status: 401,
    });
    await expect(client.search("leave", "token")).rejects.toMatchObject({
      status: 403,
    });
    expect(listener).not.toHaveBeenCalled();
  });
});
