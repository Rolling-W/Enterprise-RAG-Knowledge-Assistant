import { act, fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { AuthProvider, useAuth } from "./AuthContext";
import { api } from "../api/client";
import { toSession } from "../api/adapters";
import { tokenFixture } from "../test/fixtures";
import { createApiClient } from "../api/client";

function SessionProbe() {
  const { session, signIn } = useAuth();
  return (
    <>
      <span>{session ? session.user.username : "Signed out"}</span>
      <button
        onClick={() => void signIn("manager@enterprise.local", "demo123")}
      >
        Log in
      </button>
    </>
  );
}
it("clears the session when the backend's expires_in elapses", async () => {
  vi.useFakeTimers();
  vi.spyOn(api, "login").mockResolvedValue(
    toSession({ ...tokenFixture, expires_in: 1 }),
  );
  render(
    <AuthProvider>
      <SessionProbe />
    </AuthProvider>,
  );
  await act(async () =>
    fireEvent.click(screen.getByRole("button", { name: "Log in" })),
  );
  expect(screen.getByText("manager@enterprise.local")).toBeInTheDocument();
  await act(async () => vi.advanceTimersByTimeAsync(1000));
  expect(screen.getByText("Signed out")).toBeInTheDocument();
});

it("ignores a late 401 for an older token after a new login", async () => {
  let resolve!: (response: Response) => void;
  const client = createApiClient({ mode: "live", fetchTransport: () => new Promise((done) => { resolve = done; }) });
  vi.spyOn(api, "onUnauthorized").mockImplementation(client.onUnauthorized);
  vi.spyOn(api, "login")
    .mockResolvedValueOnce(toSession({ ...tokenFixture, access_token: "old-token" }))
    .mockResolvedValueOnce(toSession({ ...tokenFixture, access_token: "new-token", user: { ...tokenFixture.user, username: "new@enterprise.local" } }));
  render(<AuthProvider><SessionProbe /></AuthProvider>);
  await act(async () => fireEvent.click(screen.getByRole("button", { name: "Log in" })));
  const pending = client.search("leave", "old-token").catch(() => undefined);
  await act(async () => fireEvent.click(screen.getByRole("button", { name: "Log in" })));
  await act(async () => {
    resolve(new Response(JSON.stringify({ detail: "Expired" }), { status: 401 }));
    await pending;
  });
  expect(screen.getByText("new@enterprise.local")).toBeInTheDocument();
});
