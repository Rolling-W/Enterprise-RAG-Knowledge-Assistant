import { describe, expect, it, vi } from "vitest";
import { createApiClient } from "./client";
import { citationLocation, toAssistantResponse } from "./adapters";
import { searchFixture, tokenFixture, uploadFixture } from "../test/fixtures";

const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status });
describe("HTTP client and display adapters", () => {
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
  it("never falls back to mock data or calls unimplemented endpoints in live mode", async () => {
    const transport = vi.fn();
    const mock = vi.fn();
    const client = createApiClient({
      mode: "live",
      fetchTransport: transport,
      mockTransport: mock,
    });
    await expect(client.documents("token")).rejects.toMatchObject({
      status: 501,
    });
    await expect(client.document("doc", "token")).rejects.toMatchObject({
      status: 501,
    });
    await client.logout("token");
    expect(transport).not.toHaveBeenCalled();
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

  it.each([true, false])("notifies on protected 401, including JSON=%s", async (json) => {
    const client = createApiClient({
      mode: "live",
      fetchTransport: async () => json
        ? response({ detail: "Expired token" }, 401)
        : new Response("Unauthorized", { status: 401 }),
    });
    const listener = vi.fn();
    const unsubscribe = client.onUnauthorized(listener);
    await expect(client.search("leave", "expired-token")).rejects.toMatchObject({ status: 401 });
    expect(listener).toHaveBeenCalledWith("expired-token");
    unsubscribe();
    await expect(client.search("leave", "expired-token")).rejects.toMatchObject({ status: 401 });
    expect(listener).toHaveBeenCalledTimes(1);
  });

  it("keeps login errors and forbidden requests out of session invalidation", async () => {
    const transport = vi.fn()
      .mockResolvedValueOnce(response({ detail: "Invalid credentials" }, 401))
      .mockResolvedValueOnce(response({ detail: "Permission required" }, 403));
    const client = createApiClient({ mode: "live", fetchTransport: transport });
    const listener = vi.fn();
    client.onUnauthorized(listener);
    await expect(client.login("manager", "wrong")).rejects.toMatchObject({ status: 401 });
    await expect(client.search("leave", "token")).rejects.toMatchObject({ status: 403 });
    expect(listener).not.toHaveBeenCalled();
  });
});
