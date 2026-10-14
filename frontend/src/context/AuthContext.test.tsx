import { act, fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { AuthProvider, useAuth } from "./AuthContext";
import { api } from "../api/client";
import { toSession } from "../api/adapters";
import { tokenFixture } from "../test/fixtures";

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
