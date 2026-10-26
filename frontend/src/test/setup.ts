import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";
import { mockTransport } from "../mocks/handlers";

Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
  value: vi.fn(),
  configurable: true,
});
afterEach(() => {
  cleanup();
  mockTransport.reset();
  vi.useRealTimers();
  window.location.hash = "";
});
