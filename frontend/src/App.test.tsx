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
import { api, createApiClient } from "./api/client";
import { createMockTransport } from "./mocks/handlers";
import { searchFixture } from "./test/fixtures";
import type { SearchResponse } from "./api/contracts";

let mock: ReturnType<typeof createMockTransport>;
beforeEach(() => {
  mock = createMockTransport({
    latencyMs: 0,
    searchLatencyMs: 0,
    processingMs: 20,
  });
  const client = createApiClient({ mode: "mock", mockTransport: mock.handler });
  vi.spyOn(api, "login").mockImplementation(client.login);
  vi.spyOn(api, "logout").mockImplementation(client.logout);
  vi.spyOn(api, "search").mockImplementation(client.search);
  vi.spyOn(api, "upload").mockImplementation(client.upload);
  vi.spyOn(api, "documents").mockImplementation(client.documents);
  vi.spyOn(api, "document").mockImplementation(client.document);
});
afterEach(() => {
  mock.reset();
  api.mode = "mock";
});

async function signIn(role?: "Staff" | "Executive") {
  render(<App />);
  if (role) await userEvent.click(screen.getByRole("button", { name: role }));
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  await screen.findByRole("heading", { name: "Knowledge assistant", level: 1 });
}

describe("frontend independent workflows", () => {
  it("protects routes, shows login errors, and supports navigation and logout", async () => {
    window.location.hash = "#/documents";
    render(<App />);
    await screen.findByRole("button", { name: "Sign in" });
    const password = screen.getByLabelText("Password");
    await userEvent.clear(password);
    await userEvent.type(password, "incorrect");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("incorrect");
    await userEvent.clear(password);
    await userEvent.type(password, "demo123");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await screen.findByRole("heading", {
      name: "Knowledge assistant",
      level: 1,
    });
    await userEvent.click(
      within(
        screen.getByRole("navigation", { name: "Main navigation" }),
      ).getByRole("link", { name: "Document library" }),
    );
    await screen.findByText("Employee_Handbook.pdf");
    expect(
      screen.getByRole("button", { name: "Browse files" }),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
    expect(
      await screen.findByRole("button", { name: "Sign in" }),
    ).toBeInTheDocument();
  });
  it("keeps staff read-only and applies document visibility", async () => {
    await signIn("Staff");
    await userEvent.click(
      screen.getByRole("link", { name: "Browse documents" }),
    );
    await screen.findByText("Employee_Handbook.pdf");
    expect(screen.getByText(/view-only access/)).toBeInTheDocument();
    expect(
      screen.queryByLabelText("Choose a document"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Manager_Playbook.pdf")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Leadership_Strategy.pdf"),
    ).not.toBeInTheDocument();
  });
  it("uploads and refreshes the library, including processing completion and an empty search", async () => {
    await signIn();
    await userEvent.click(
      screen.getByRole("link", { name: "Browse documents" }),
    );
    await screen.findByText("Employee_Handbook.pdf");
    await userEvent.upload(
      screen.getByLabelText("Choose a document"),
      new File(["pdf"], "weekly-policy.pdf"),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Upload document" }),
    );
    const row = await screen.findByRole("row", { name: /weekly-policy.pdf/ });
    await waitFor(
      () => expect(within(row).getByText("Ready")).toBeInTheDocument(),
      { timeout: 2500 },
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: "Search documents by name" }),
      "missing-document",
    );
    expect(
      screen.getByRole("heading", { name: "No matching documents" }),
    ).toBeInTheDocument();
  });
  it("sends with Enter, opens a cited source and restores focus when closing", async () => {
    await signIn();
    const input = screen.getByRole("textbox", {
      name: "Ask a question about your documents",
    });
    await userEvent.type(input, "What is the remote work policy?");
    await userEvent.keyboard("{Enter}");
    const source = await screen.findByRole("button", {
      name: /Remote_Work_Policy.md/,
    });
    expect(source).toHaveTextContent("Source excerpt");
    await userEvent.click(source);
    const dialog = await screen.findByRole("dialog");
    expect(
      within(dialog).getByRole("heading", { name: "Remote_Work_Policy.md" }),
    ).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(source).toHaveFocus();
  });
  it("handles failed searches and retry, then clears the conversation", async () => {
    await signIn();
    mock.next("/api/v1/search", "server-error");
    const input = screen.getByRole("textbox", {
      name: "Ask a question about your documents",
    });
    await userEvent.type(input, "annual leave");
    await userEvent.click(
      screen.getByRole("button", { name: "Send question" }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "Try again" }),
    );
    await screen.findByRole("button", { name: /Employee_Handbook.pdf/ });
    await userEvent.click(
      screen.getByRole("button", { name: "New conversation" }),
    );
    expect(
      screen.getByRole("heading", { name: "What would you like to know?" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Employee_Handbook.pdf/ }),
    ).not.toBeInTheDocument();
  });
  it("blocks duplicate sends and ignores a late response after a new conversation", async () => {
    await signIn();
    let resolve!: (response: SearchResponse) => void;
    vi.mocked(api.search).mockImplementationOnce(
      () =>
        new Promise((done) => {
          resolve = done;
        }),
    );
    const input = screen.getByRole("textbox", {
      name: "Ask a question about your documents",
    });
    await userEvent.type(input, "annual leave");
    fireEvent.keyDown(input, { key: "Enter", code: "Enter" });
    expect(input).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Send question" }),
    ).toBeDisabled();
    await userEvent.click(
      screen.getByRole("button", { name: "New conversation" }),
    );
    await act(async () => resolve(searchFixture));
    expect(
      screen.getByRole("heading", { name: "What would you like to know?" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Employee_Handbook.pdf/ }),
    ).not.toBeInTheDocument();
  });
  it("uses live citation excerpts and keeps pending document endpoints out of the UI workflow", async () => {
    await signIn();
    api.mode = "live";
    vi.mocked(api.search).mockResolvedValueOnce(searchFixture);
    await userEvent.type(
      screen.getByRole("textbox", {
        name: "Ask a question about your documents",
      }),
      "annual leave",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Send question" }),
    );
    const source = await screen.findByRole("button", {
      name: /Employee_Handbook.pdf/,
    });
    expect(source).toHaveTextContent("Page 12 · Lines 45–49");
    await userEvent.click(source);
    expect(
      within(screen.getByRole("dialog")).getByText(
        searchFixture.results[0].content,
      ),
    ).toBeInTheDocument();
    expect(api.document).not.toHaveBeenCalled();
    await userEvent.keyboard("{Escape}");
    await userEvent.click(
      screen.getByRole("link", { name: "Browse documents" }),
    );
    expect(await screen.findByRole("status")).toHaveTextContent(
      "document library is not available yet",
    );
    expect(api.documents).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Choose a document")).toBeInTheDocument();
  });
});
