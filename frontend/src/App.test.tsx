import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { api, ApiError, createApiClient } from "./api/client";
import { createMockTransport } from "./mocks/handlers";
import { searchFixture } from "./test/fixtures";
import type { Conversation } from "./api/contracts";

let mock: ReturnType<typeof createMockTransport>;
let client: ReturnType<typeof createApiClient>;
beforeEach(() => {
  api.mode = "mock";
  mock = createMockTransport({
    latencyMs: 0,
    searchLatencyMs: 0,
    processingMs: 20,
  });
  client = createApiClient({ mode: "mock", mockTransport: mock.handler });
  for (const name of [
    "onUnauthorized",
    "login",
    "logout",
    "search",
    "upload",
    "documents",
    "document",
    "documentChunk",
    "changePermission",
    "deleteDocument",
    "reindexDocument",
    "conversations",
    "conversation",
    "createConversation",
    "sendMessage",
    "deleteConversation",
    "debugSearch",
  ] as const) {
    vi.spyOn(api, name).mockImplementation(client[name] as never);
  }
});
afterEach(() => {
  mock.reset();
  api.mode = "mock";
});
async function signIn(role?: "User" | "Admin") {
  render(<App />);
  if (role) await userEvent.click(screen.getByRole("button", { name: role }));
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  await screen.findByRole("heading", { name: "Knowledge assistant", level: 1 });
}
async function ask(query = "annual leave") {
  await userEvent.type(
    screen.getByRole("textbox", {
      name: "Ask a question about your documents",
    }),
    query,
  );
  await userEvent.click(screen.getByRole("button", { name: "Send question" }));
}
async function documents() {
  await userEvent.click(screen.getByRole("link", { name: "Browse documents" }));
  await screen.findByText("Employee_Handbook.pdf");
}
describe("Sprint 4 frontend workflows", () => {
  it("paginates the document catalog and resets to the first page when filters change", async () => {
    await signIn("Admin");
    const token = (await vi.mocked(api.login).mock.results[0].value)
      .access_token;
    const template = (await client.documents(token)).items[0];
    const catalog = Array.from({ length: 21 }, (_, index) => ({
      ...template,
      document_id: String(index),
      filename: `Policy-${index}.txt`,
      title: `Policy-${index}.txt`,
    }));
    vi.mocked(api.documents).mockImplementation(async (_token, params = {}) => {
      const page = params.page ?? 1,
        page_size = params.page_size ?? 20;
      const items = params.q
        ? catalog.filter((item) => item.title.includes(params.q!))
        : catalog;
      return {
        items: items.slice((page - 1) * page_size, page * page_size),
        page,
        page_size,
        total: items.length,
      };
    });
    await userEvent.click(
      screen.getByRole("link", { name: "Browse documents" }),
    );
    await screen.findByText("Policy-0.txt");
    await userEvent.click(screen.getByRole("button", { name: "Next page" }));
    expect(await screen.findByText("Policy-20.txt")).toBeInTheDocument();
    expect(screen.queryByText("Policy-0.txt")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next page" })).toBeDisabled();
    await userEvent.type(
      screen.getByLabelText("Search documents by name"),
      "Policy-0",
    );
    expect(await screen.findByText("Policy-0.txt")).toBeInTheDocument();
    expect(await screen.findByText("Page 1 of 1")).toBeInTheDocument();
  });
  it("paginates history and handles a missing conversation without restoring stale content", async () => {
    const history = Array.from({ length: 21 }, (_, index) => ({
      conversation_id: String(index),
      title: `Saved ${index}`,
      created_at: "2026-11-01T10:00:00Z",
      updated_at: "2026-11-01T10:00:00Z",
    }));
    vi.mocked(api.conversations).mockImplementation(
      async (_token, page = 1) => ({
        items: history.slice((page - 1) * 20, page * 20),
        page,
        page_size: 20,
        total: 21,
      }),
    );
    await signIn();
    await userEvent.click(
      await screen.findByRole("button", { name: "Next history page" }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: /Saved 20.*2026/ }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "unavailable or belongs to another account",
    );
    expect(
      screen.getByRole("textbox", {
        name: "Ask a question about your documents",
      }),
    ).toBeDisabled();
    await userEvent.click(
      screen.getByRole("button", { name: "New conversation" }),
    );
    expect(
      screen.getByRole("textbox", {
        name: "Ask a question about your documents",
      }),
    ).toBeEnabled();
    expect(
      screen.queryByText("Scoring diagnostics (development)"),
    ).not.toBeInTheDocument();
  });
  it("does not render cached citation content after the detail endpoint denies access", async () => {
    await signIn();
    await userEvent.click(screen.getByLabelText("Save conversation"));
    await ask();
    const source = await screen.findByRole("button", {
      name: /Employee_Handbook.pdf/,
    });
    vi.mocked(api.document).mockRejectedValueOnce(
      new ApiError("Not Found", 404),
    );
    await userEvent.click(source);
    const drawer = screen.getByRole("dialog");
    expect(await within(drawer).findByRole("alert")).toHaveTextContent(
      "unavailable or you no longer have access",
    );
    expect(
      within(drawer).queryByText(/Full-time employees receive 20 days/),
    ).not.toBeInTheDocument();
    expect(within(drawer).getByText("Page 12")).toBeInTheDocument();
  });
  it("protects routes and clears only the active session on a protected 401", async () => {
    window.location.hash = "#/documents";
    render(<App />);
    await screen.findByRole("button", { name: "Sign in" });
    await userEvent.clear(screen.getByLabelText("Password"));
    await userEvent.type(screen.getByLabelText("Password"), "incorrect");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("incorrect");
    await userEvent.clear(screen.getByLabelText("Password"));
    await userEvent.type(screen.getByLabelText("Password"), "demo123");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await screen.findByRole("heading", {
      name: "Knowledge assistant",
      level: 1,
    });
    mock.reset();
    await ask();
    expect(
      await screen.findByRole("button", { name: "Sign in" }),
    ).toBeInTheDocument();
    expect(api.logout).not.toHaveBeenCalled();
  });
  it("allows managers Level 2 reads but only Level 1 uploads; ordinary users are read-only", async () => {
    await signIn();
    await documents();
    expect(
      screen
        .getByLabelText("Document permission level")
        .querySelectorAll("option"),
    ).toHaveLength(1);
    expect(
      screen.queryByRole("button", { name: /Delete Employee/ }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Manager_Playbook.pdf")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
    await userEvent.click(screen.getByRole("button", { name: "User" }));
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await screen.findByRole("heading", {
      name: "Knowledge assistant",
      level: 1,
    });
    await documents();
    expect(screen.getByText(/view-only access/)).toBeInTheDocument();
    expect(
      screen.queryByLabelText("Choose a document"),
    ).not.toBeInTheDocument();
  });
  it("uploads the admin-selected permission and refreshes real document status", async () => {
    await signIn("Admin");
    await documents();
    await userEvent.selectOptions(
      screen.getByLabelText("Document permission level"),
      "3",
    );
    await userEvent.upload(
      screen.getByLabelText("Choose a document"),
      new File(["policy"], "weekly-policy.pdf"),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Upload document" }),
    );
    const row = await screen.findByRole("row", { name: /weekly-policy.pdf/ });
    expect(api.upload).toHaveBeenCalledWith(
      expect.any(File),
      expect.any(String),
      3,
    );
    expect(within(row).getByText("Level 3")).toBeInTheDocument();
    await waitFor(
      () =>
        expect(
          screen.getByRole("row", { name: /weekly-policy.pdf/ }),
        ).toHaveTextContent("Ready"),
      { timeout: 3500 },
    );
  });
  it("uses backend-provided actions even when a local admin role could manage", async () => {
    await signIn("Admin");
    vi.mocked(api.documents).mockImplementation(async (...args) => {
      const result = await client.documents(...args);
      return {
        ...result,
        items: result.items.map((item) => ({
          ...item,
          available_actions: ["read"],
        })),
      };
    });
    await documents();
    expect(
      screen.queryByRole("button", { name: /Delete Employee/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Details Employee_Handbook.pdf" }),
    ).toBeInTheDocument();
  });
  it("searches on the server, sends filters/sort/pagination and handles empty results", async () => {
    await signIn("Admin");
    await documents();
    await userEvent.selectOptions(
      screen.getByLabelText("Sort by"),
      "permission_level",
    );
    await userEvent.selectOptions(screen.getByLabelText("Sort order"), "asc");
    await userEvent.selectOptions(
      screen.getByLabelText("Permission level"),
      "2",
    );
    await waitFor(() =>
      expect(
        screen.queryByText("Employee_Handbook.pdf"),
      ).not.toBeInTheDocument(),
    );
    expect(await screen.findByText("Manager_Playbook.pdf")).toBeInTheDocument();
    await userEvent.type(
      screen.getByLabelText("Search documents by name"),
      "missing-document",
    );
    expect(
      await screen.findByRole("heading", { name: "No matching documents" }),
    ).toBeInTheDocument();
    expect(api.documents).toHaveBeenLastCalledWith(
      expect.any(String),
      expect.objectContaining({
        q: "missing-document",
        permission_level: 2,
        sort_by: "permission_level",
        sort_order: "asc",
        page: 1,
      }),
    );
  });
  it("shows document details and completes permission changes, re-index and confirmed deletion", async () => {
    await signIn("Admin");
    await documents();
    await userEvent.click(
      screen.getByRole("button", { name: "Details Employee_Handbook.pdf" }),
    );
    const source = await screen.findByRole("dialog");
    expect(
      await within(source).findByText("Demo administrator"),
    ).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    await userEvent.click(
      screen.getByRole("button", {
        name: "Change permission Employee_Handbook.pdf",
      }),
    );
    await userEvent.selectOptions(
      screen.getByLabelText("New permission level"),
      "2",
    );
    await userEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Confirm",
      }),
    );
    await waitFor(() =>
      expect(
        screen.getByRole("row", { name: /Employee_Handbook.pdf/ }),
      ).toHaveTextContent("Level 2"),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Re-index Employee_Handbook.pdf" }),
    );
    await userEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Confirm",
      }),
    );
    await screen.findByText("Re-indexing started.");
    await userEvent.click(
      screen.getByRole("button", { name: "Refresh documents" }),
    );
    await waitFor(
      () =>
        expect(
          screen.getByRole("button", { name: "Delete Employee_Handbook.pdf" }),
        ).toBeEnabled(),
      { timeout: 3500 },
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Delete Employee_Handbook.pdf" }),
    );
    await userEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Cancel",
      }),
    );
    expect(api.deleteDocument).not.toHaveBeenCalled();
    await userEvent.click(
      screen.getByRole("button", { name: "Delete Employee_Handbook.pdf" }),
    );
    mock.next("/api/v1/documents/doc-handbook", "server-error");
    await userEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Confirm",
      }),
    );
    expect(
      await within(screen.getByRole("dialog")).findByRole("alert"),
    ).toHaveTextContent("temporarily unavailable");
    expect(
      screen.getByRole("row", { name: /Employee_Handbook.pdf/ }),
    ).toBeInTheDocument();
    await userEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Confirm",
      }),
    );
    await waitFor(() =>
      expect(
        screen.queryByRole("row", { name: /Employee_Handbook.pdf/ }),
      ).not.toBeInTheDocument(),
    );
  });
  it("saves and reloads messages/citations across navigation, and deletes a saved conversation", async () => {
    await signIn();
    await ask();
    expect(
      await screen.findByRole("button", { name: /Employee_Handbook.pdf/ }),
    ).toHaveTextContent("Page 12");
    expect(api.sendMessage).toHaveBeenCalledWith(
      expect.any(String),
      "annual leave",
      expect.any(String),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "New conversation" }),
    );
    expect(
      screen.getByRole("heading", { name: "What would you like to know?" }),
    ).toBeInTheDocument();
    await userEvent.click(
      await screen.findByRole("button", { name: /annual leave.*2026/ }),
    );
    expect(
      await screen.findByRole("button", { name: /Employee_Handbook.pdf/ }),
    ).toHaveTextContent("Page 12");
    await documents();
    await userEvent.click(
      screen.getByRole("link", { name: "Knowledge assistant" }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: /annual leave.*2026/ }),
    );
    expect(
      await screen.findByRole("button", { name: /Employee_Handbook.pdf/ }),
    ).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "Delete conversation annual leave" }),
    );
    await userEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Confirm",
      }),
    );
    expect(
      await screen.findByText("No saved conversations yet."),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Employee_Handbook.pdf/ }),
    ).not.toBeInTheDocument();
  });
  it("marks revoked citations unavailable on restore without displaying cached source content", async () => {
    await signIn("User");
    await ask();
    await screen.findByRole("button", { name: /Employee_Handbook.pdf/ });
    const admin = await client.login("executive@enterprise.local", "demo123");
    await client.changePermission("doc-handbook", 2, admin.access_token);
    await userEvent.click(
      screen.getByRole("button", { name: "New conversation" }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: /annual leave.*2026/ }),
    );
    const source = await screen.findByRole("button", {
      name: /Unavailable source/,
    });
    expect(source).toBeDisabled();
    expect(source).toHaveTextContent("Page 12");
    expect(
      screen.queryByText(/Full-time employees receive 20 days/),
    ).not.toBeInTheDocument();
  });
  it.each(["keyword", "semantic", "hybrid"] as const)(
    "supports explicit unsaved %s search, scores, and citation preview focus",
    async (mode) => {
      await signIn();
      await userEvent.click(screen.getByLabelText("Save conversation"));
      await userEvent.selectOptions(screen.getByLabelText("Search mode"), mode);
      await ask();
      const source = await screen.findByRole("button", {
        name: /Employee_Handbook.pdf/,
      });
      expect(api.search).toHaveBeenCalledWith(
        "annual leave",
        expect.any(String),
        { search_mode: mode },
      );
      expect(source).toHaveTextContent("Score 0.920");
      await userEvent.click(source);
      expect(
        await within(screen.getByRole("dialog")).findByText(
          /Full-time employees receive 20 days/,
        ),
      ).toBeInTheDocument();
      await userEvent.keyboard("{Escape}");
      expect(source).toHaveFocus();
    },
  );
  it("preserves the original retrieval mode on unsaved retry and keeps 403 signed in", async () => {
    await signIn();
    await userEvent.click(screen.getByLabelText("Save conversation"));
    await userEvent.selectOptions(
      screen.getByLabelText("Search mode"),
      "keyword",
    );
    vi.mocked(api.search).mockRejectedValueOnce(
      new ApiError("Permission required", 403),
    );
    await ask();
    expect(await screen.findByText("Permission required")).toBeInTheDocument();
    await userEvent.selectOptions(
      screen.getByLabelText("Search mode"),
      "semantic",
    );
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    await screen.findByRole("button", { name: /Employee_Handbook.pdf/ });
    expect(api.search).toHaveBeenLastCalledWith(
      "annual leave",
      expect.any(String),
      { search_mode: "keyword" },
    );
  });
  it("explains unsupported persistence and uses live search without a mock fallback", async () => {
    await signIn();
    vi.mocked(api.createConversation).mockRejectedValueOnce(
      new ApiError("Not Found", 404),
    );
    vi.mocked(api.search).mockResolvedValueOnce(searchFixture);
    await ask();
    expect(
      await screen.findByText(
        /This conversation is search-only and will not be saved/,
      ),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("button", { name: /Employee_Handbook.pdf/ }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Save conversation")).not.toBeChecked();
    expect(api.sendMessage).not.toHaveBeenCalled();
  });
  it("does not fall back to unsaved search on forbidden conversation creation", async () => {
    await signIn();
    vi.mocked(api.createConversation).mockRejectedValueOnce(
      new ApiError("Forbidden", 403),
    );
    await ask();
    expect(await screen.findByText("Forbidden")).toBeInTheDocument();
    expect(api.search).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Save conversation")).toBeChecked();
  });
  it("requires reload after an ambiguous saved-message failure instead of duplicating a turn", async () => {
    await signIn();
    vi.mocked(api.sendMessage).mockRejectedValueOnce(
      new ApiError("Connection interrupted", 0),
    );
    await ask();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Reload this conversation before sending again",
    );
    expect(
      screen.getByRole("button", { name: "Send question" }),
    ).toBeDisabled();
    expect(
      screen.queryByRole("button", { name: "Try again" }),
    ).not.toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "Reload conversation" }),
    );
    await waitFor(() =>
      expect(
        screen.getByRole("textbox", {
          name: "Ask a question about your documents",
        }),
      ).toBeEnabled(),
    );
  });
  it("ignores a late saved turn after starting a new conversation", async () => {
    await signIn();
    let resolve!: () => void;
    vi.mocked(api.sendMessage).mockImplementationOnce(
      () =>
        new Promise((done) => {
          resolve = () => done(undefined);
        }),
    );
    await ask();
    await waitFor(() => expect(api.sendMessage).toHaveBeenCalledOnce());
    expect(
      screen.getByRole("button", { name: "Send question" }),
    ).toBeDisabled();
    await userEvent.click(
      screen.getByRole("button", { name: "New conversation" }),
    );
    await act(async () => resolve());
    expect(
      screen.getByRole("heading", { name: "What would you like to know?" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Employee_Handbook.pdf/ }),
    ).not.toBeInTheDocument();
  });
  it("ignores a late restore response after switching conversations", async () => {
    await signIn();
    await ask("annual leave");
    await screen.findByRole("button", { name: /Employee_Handbook.pdf/ });
    await userEvent.click(
      screen.getByRole("button", { name: "New conversation" }),
    );
    await ask("remote work");
    await screen.findByRole("button", { name: /Remote_Work_Policy.md/ });
    let resolve!: (value: Conversation) => void;
    const firstId = vi.mocked(api.createConversation).mock.results[0];
    const first = await firstId.value;
    const stale = await client.conversation(
      first.conversation_id,
      vi.mocked(api.login).mock.results[0]
        ? (await vi.mocked(api.login).mock.results[0].value).access_token
        : "",
    );
    vi.mocked(api.conversation).mockImplementationOnce(
      () =>
        new Promise((done) => {
          resolve = done;
        }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: /annual leave.*2026/ }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: /remote work.*2026/ }),
    );
    await screen.findByRole("button", { name: /Remote_Work_Policy.md/ });
    await act(async () => resolve(stale));
    expect(
      screen.queryByRole("button", { name: /Employee_Handbook.pdf/ }),
    ).not.toBeInTheDocument();
  });
  it("shows unavailable document API errors with retry while retaining uploads", async () => {
    await signIn();
    vi.mocked(api.documents).mockRejectedValueOnce(
      new ApiError("Not Found", 404),
    );
    await userEvent.click(
      screen.getByRole("link", { name: "Browse documents" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "not available on this backend yet",
    );
    expect(screen.getByLabelText("Choose a document")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(
      await screen.findByText("Employee_Handbook.pdf"),
    ).toBeInTheDocument();
  });
  it("offers admin-only development diagnostics including stage scores and timings", async () => {
    await signIn("Admin");
    fireEvent.click(screen.getByText("Scoring diagnostics (development)"));
    await userEvent.type(
      screen.getByLabelText("Debug query"),
      "leave strategy",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Inspect scoring" }),
    );
    expect(
      await screen.findByRole("table", {
        name: "Candidate scores and final ranking",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("18.00 ms")).toBeInTheDocument();
    expect(
      screen.getByText("Demo scores and timings are simulated."),
    ).toBeInTheDocument();
  });
});
