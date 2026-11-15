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
  client.login(role + "@enterprise.local", "demo123");
describe("Sprint 4 mock contract", () => {
  it("returns server roles/permissions and rejects expired or revoked sessions", async () => {
    const session = await login();
    expect(session.user).toMatchObject({
      role: "staff",
      permissions: ["document:read", "document:upload"],
    });
    await expect(client.search("leave", "missing")).rejects.toMatchObject({
      status: 401,
    });
    const actualNow = Date.now();
    const clock = vi.spyOn(Date, "now").mockReturnValue(actualNow + 3600001);
    await expect(
      client.search("leave", session.access_token),
    ).rejects.toMatchObject({ status: 401 });
    clock.mockRestore();
    await client.logout(session.access_token);
    await expect(client.documents(session.access_token)).rejects.toMatchObject({
      status: 401,
    });
  });

  it.each(["keyword", "semantic", "hybrid"] as const)(
    "enforces clearance and department RBAC before %s retrieval",
    async (mode) => {
      const manager = await login("manager");
      const staff = await login("staff");
      const admin = await login("executive");

      // Department Manager: General / Global, Level 1–2
      const managerDocuments = await client.documents(manager.access_token);

      expect(
        managerDocuments.items.map((item) => item.permission_level),
      ).toEqual([1, 1, 1, 2]);

      expect(
        (await client.documents(manager.access_token, {
          permission_level: 2,
        })).total,
      ).toBe(1);

      expect(
        (await client.document("doc-manager", manager.access_token))
          .permission_level,
      ).toBe(2);

      await expect(
        client.document("doc-strategy", manager.access_token),
      ).rejects.toMatchObject({ status: 404 });

      // Standard Staff: General / Global, Level 1 only
      const staffDocuments = await client.documents(staff.access_token);

      expect(
        staffDocuments.items.map((item) => item.permission_level),
      ).toEqual([1, 1, 1]);

      expect(
        (await client.documents(staff.access_token, {
          permission_level: 2,
        })).total,
      ).toBe(0);

      await expect(
        client.document("doc-manager", staff.access_token),
      ).rejects.toMatchObject({ status: 404 });

      // Search must enforce the same RBAC rules.
      const managerResults = await client.search(
        "leave manager strategy",
        manager.access_token,
        { search_mode: mode },
      );

      expect(
        managerResults.results.some(
          (item) => item.document_id === "doc-manager",
        ),
      ).toBe(true);

      expect(
        managerResults.results.every(
          (item) => item.permission_level! <= 2,
        ),
      ).toBe(true);

      const staffResults = await client.search(
        "leave manager strategy",
        staff.access_token,
        { search_mode: mode },
      );

      expect(
        staffResults.results.every(
          (item) => item.permission_level === 1,
        ),
      ).toBe(true);

      // Client filters must not bypass authorization.
      for (const token of [
        manager.access_token,
        staff.access_token,
      ]) {
        expect(
          (await client.search("strategy", token, {
            filters: { permission_level: 3 },
          })).results,
        ).toEqual([]);
      }

      // Executive can access all departments and levels.
      expect(
        (await client.documents(admin.access_token)).total,
      ).toBe(5);

      expect(
        (await client.search("manager strategy", admin.access_token, {
          search_mode: mode,
        })).results,
      ).toHaveLength(2);
    },
  );

  it("defaults uploads to Level 1, restricts staff selection and denies user uploads", async () => {
    const staff = await login(),
      user = await login("staff"),
      admin = await login("executive");
    const file = new File(["policy"], "policy.txt");
    const uploaded = await client.upload(file, staff.access_token);
    expect(uploaded).toMatchObject({
      permission_level: 1,
      status: "processing",
      creator: { user_id: staff.user.user_id },
    });
    await expect(
      client.upload(file, staff.access_token, 2),
    ).rejects.toMatchObject({ status: 403 });
    await expect(
      client.upload(file, user.access_token, 1),
    ).rejects.toMatchObject({ status: 403 });
    expect(
      (await client.upload(file, admin.access_token, 3)).permission_level,
    ).toBe(3);
    for (const level of ["0", "4", "1.5", "invalid"]) {
      const body = new FormData();
      body.append("file", file);
      body.append("permission_level", level);
      expect(
        (
          await mock.handler("/api/v1/upload", {
            method: "POST",
            headers: { Authorization: "Bearer " + admin.access_token },
            body,
          })
        ).status,
      ).toBe(422);
    }
  });
  it("filters and paginates on the authorized set and sorts deterministically", async () => {
    const { access_token } = await login("executive");
    const first = await client.documents(access_token, {
      page: 1,
      page_size: 2,
      sort_by: "permission_level",
      sort_order: "desc",
    });
    expect(first).toMatchObject({ page: 1, page_size: 2, total: 5 });
    expect(first.items.map((item) => item.permission_level)).toEqual([3, 2]);
    expect(
      (await client.documents(access_token, { page: 2, page_size: 2 })).items,
    ).toHaveLength(2);
    expect(
      (
        await client.documents(access_token, {
          q: "benefits",
          creator_id: "demo-seed",
          status: "indexed",
        })
      ).items[0].document_id,
    ).toBe("doc-handbook");
    expect(
      (await client.documents(access_token, { creator_id: "missing" })).total,
    ).toBe(0);
  });
  it("updates permission, re-indexes and deletes; mutation failures leave state intact", async () => {
    vi.useFakeTimers();
    const admin = await login("executive"),
      staff = await login("staff");
    expect(
      (await client.document("doc-handbook", staff.access_token))
        .available_actions,
    ).toEqual(["read"]);
    await expect(
      client.changePermission("doc-handbook", 2, staff.access_token),
    ).rejects.toMatchObject({ status: 403 });
    await expect(
      client.reindexDocument("doc-handbook", staff.access_token),
    ).rejects.toMatchObject({ status: 403 });
    await expect(
      client.deleteDocument("doc-handbook", staff.access_token),
    ).rejects.toMatchObject({ status: 403 });
    await client.changePermission("doc-handbook", 2, admin.access_token);
    expect((await client.search("leave", staff.access_token)).results).toEqual(
      [],
    );
    await client.reindexDocument("doc-handbook", admin.access_token);
    expect(
      (await client.document("doc-handbook", admin.access_token)).status,
    ).toBe("processing");
    await vi.advanceTimersByTimeAsync(20);
    expect(
      (await client.document("doc-handbook", admin.access_token)).status,
    ).toBe("indexed");
    mock.next("/api/v1/documents/doc-handbook", "server-error");
    await expect(
      client.deleteDocument("doc-handbook", admin.access_token),
    ).rejects.toMatchObject({ status: 503 });
    expect(
      (await client.document("doc-handbook", admin.access_token))
        .permission_level,
    ).toBe(2);
    await client.deleteDocument("doc-handbook", admin.access_token);
    await expect(
      client.document("doc-handbook", admin.access_token),
    ).rejects.toMatchObject({ status: 404 });
    expect((await client.search("leave", admin.access_token)).results).toEqual(
      [],
    );
  });
  it("persists ordered owner-only messages and rechecks citations after permission changes", async () => {
    const staff = await login("staff"),
      admin = await login("executive"),
      other = await login("other");
    const conversation = await client.createConversation(
      staff.access_token,
      "Benefits",
    );
    await client.sendMessage(
      conversation.conversation_id,
      "annual leave",
      staff.access_token,
    );
    await client.sendMessage(
      conversation.conversation_id,
      "remote work",
      staff.access_token,
    );
    const restored = await client.conversation(
      conversation.conversation_id,
      staff.access_token,
    );
    expect(restored.messages.map((item) => item.sequence)).toEqual([
      1, 2, 3, 4,
    ]);
    expect(restored.messages[1].citations[0]).toMatchObject({
      document_id: "doc-handbook",
      chunk_id: "doc-handbook-chunk-1",
      page: 12,
    });
    await expect(
      client.conversation(conversation.conversation_id, other.access_token),
    ).rejects.toMatchObject({ status: 404 });
    await expect(
      client.deleteConversation(
        conversation.conversation_id,
        other.access_token,
      ),
    ).rejects.toMatchObject({ status: 404 });
    expect((await client.conversations(other.access_token)).total).toBe(0);
    await client.changePermission("doc-handbook", 2, admin.access_token);
    const revoked = await client.conversation(
      conversation.conversation_id,
      staff.access_token,
    );
    expect(revoked.messages[1].citations[0]).toMatchObject({
      unavailable: true,
      title: "Unavailable source",
      page: 12,
    });
    expect(revoked.messages[1].content).not.toContain("20 days");
    await client.deleteConversation(
      conversation.conversation_id,
      staff.access_token,
    );
    await expect(
      client.conversation(conversation.conversation_id, staff.access_token),
    ).rejects.toMatchObject({ status: 404 });
    expect((await client.conversations(staff.access_token)).total).toBe(0);
  });
  it.each(["keyword", "semantic", "hybrid"] as const)(
    "returns stage-aware %s diagnostics to admins only",
    async (mode) => {
      const admin = await login("executive"),
        staff = await login(),
        user = await login("staff");
      for (const token of [staff.access_token, user.access_token])
        await expect(
          client.debugSearch({ query: "leave", search_mode: mode }, token),
        ).rejects.toMatchObject({ status: 403 });
      const debug = await client.debugSearch(
        {
          query: "leave strategy",
          search_mode: mode,
          top_k: 1,
          candidate_limit: 5,
        },
        admin.access_token,
      );
      expect(debug.top_k).toBe(1);
      expect(debug.candidates).toHaveLength(2);
      expect(debug.candidates[0].scores.rerank).toBeNull();
      expect(debug.candidates[0].scores.bm25_raw === null).toBe(
        mode === "semantic",
      );
      expect(debug.candidates[0].scores.dense_raw === null).toBe(
        mode === "keyword",
      );
      expect(Object.values(debug.timings_ms).every((value) => value >= 0)).toBe(
        true,
      );
    },
  );
  it.each([0, 21, 1.5])("validates top_k %s", async (top_k) => {
    const { access_token } = await login();
    await expect(
      client.search("leave", access_token, { top_k }),
    ).rejects.toMatchObject({ status: 422 });
  });
  it("supports upload processing failures and rejects invalid files", async () => {
    const { access_token } = await login();
    await expect(
      client.upload(new File([], "empty.txt"), access_token),
    ).rejects.toMatchObject({ status: 400 });
    await expect(
      client.upload(new File(["exe"], "bad.exe"), access_token),
    ).rejects.toMatchObject({ status: 400 });
    vi.useFakeTimers();
    const uploaded = await client.upload(
      new File(["text"], "processing-error.pdf"),
      access_token,
    );
    await vi.advanceTimersByTimeAsync(20);
    expect(
      (await client.document(uploaded.document_id, access_token)).status,
    ).toBe("failed");
  });
});
