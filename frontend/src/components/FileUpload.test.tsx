import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { FileUpload } from "./FileUpload";
import { uploadFixture } from "../test/fixtures";
import { MAX_FILE_BYTES } from "../uploadPolicy";

describe("FileUpload", () => {
  it("shows indexed completion from the real upload contract without suggesting pending processing", async () => {
    const indexed = { ...uploadFixture, status: "indexed" as const, message: "Indexed 3 chunks for General with clearance 2" };
    const onUploaded = vi.fn();
    render(<FileUpload onUpload={vi.fn().mockResolvedValue(indexed)} onUploaded={onUploaded} trackProcessing={false} />);
    await userEvent.upload(screen.getByLabelText("Choose a document"), new File(["policy"], "policy.md"));
    await userEvent.click(screen.getByRole("button", { name: "Upload document" }));
    expect(await screen.findByRole("status")).toHaveTextContent("policy.md is indexed and ready to search");
    expect(screen.getByRole("status")).toHaveTextContent("Indexed 3 chunks");
    expect(screen.getByRole("status")).not.toHaveTextContent("Track its processing");
    expect(onUploaded).toHaveBeenCalledWith(indexed);
  });
  it.each(["policy.pdf", "policy.md", "policy.txt"])(
    "selects and uploads %s",
    async (name) => {
      const upload = vi
        .fn()
        .mockResolvedValue({ ...uploadFixture, filename: name });
      const uploaded = vi.fn();
      render(<FileUpload onUpload={upload} onUploaded={uploaded} />);
      await userEvent.upload(
        screen.getByLabelText("Choose a document"),
        new File(["policy"], name),
      );
      await userEvent.click(
        screen.getByRole("button", { name: "Upload document" }),
      );
      expect(upload).toHaveBeenCalledTimes(1);
      expect(upload.mock.calls[0][0].name).toBe(name);
      expect(uploaded).toHaveBeenCalledOnce();
      expect(screen.getByRole("status")).toHaveTextContent(
        `${name} was received`,
      );
    },
  );
  it("supports dragging and removing a selection", () => {
    const { container } = render(<FileUpload onUpload={vi.fn()} />);
    const dropzone = container.querySelector(".dropzone")!;
    fireEvent.dragOver(dropzone);
    expect(dropzone).toHaveClass("dragging");
    fireEvent.drop(dropzone, {
      dataTransfer: { files: [new File(["pdf"], "policy.pdf")] },
    });
    expect(screen.getByText("policy.pdf")).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Remove selected file" }),
    );
    expect(
      screen.queryByRole("button", { name: "Upload document" }),
    ).not.toBeInTheDocument();
  });
  it("rejects unsupported, empty, oversized, and multiple files", () => {
    const upload = vi.fn();
    const { container } = render(<FileUpload onUpload={upload} />);
    const dropzone = container.querySelector(".dropzone")!;
    const oversized = new File(["data"], "large.pdf");
    Object.defineProperty(oversized, "size", { value: MAX_FILE_BYTES + 1 });
    for (const file of [
      new File(["data"], "data.exe"),
      new File([], "empty.txt"),
      oversized,
    ]) {
      fireEvent.drop(dropzone, { dataTransfer: { files: [file] } });
      expect(screen.getByRole("alert")).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Upload document" }),
      ).not.toBeInTheDocument();
    }
    fireEvent.drop(dropzone, {
      dataTransfer: {
        files: [new File(["data"], "one.txt"), new File(["data"], "two.txt")],
      },
    });
    expect(screen.getByRole("alert")).toHaveTextContent("one file at a time");
    expect(upload).not.toHaveBeenCalled();
  });
  it("blocks duplicate submissions while uploading and allows retry after failure", async () => {
    let reject!: (error: Error) => void;
    const upload = vi
      .fn()
      .mockImplementationOnce(
        () =>
          new Promise((_, fail) => {
            reject = fail;
          }),
      )
      .mockResolvedValueOnce(uploadFixture);
    render(<FileUpload onUpload={upload} />);
    await userEvent.upload(
      screen.getByLabelText("Choose a document"),
      new File(["policy"], "policy.md"),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Upload document" }),
    );
    expect(screen.getByRole("button", { name: "Uploading…" })).toBeDisabled();
    expect(screen.getByLabelText("Choose a document")).toBeDisabled();
    await act(async () => reject(new Error("Upload unavailable")));
    expect(screen.getByRole("alert")).toHaveTextContent("Upload unavailable");
    await userEvent.click(
      screen.getByRole("button", { name: "Upload document" }),
    );
    expect(upload).toHaveBeenCalledTimes(2);
    expect(screen.getByRole("status")).toHaveTextContent(
      "policy.md was received",
    );
  });
});
