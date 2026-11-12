import { useEffect, useId, useRef, useState, type DragEvent } from "react";
import { Icon } from "./Icon";
import { fileSize, validateFile } from "../uploadPolicy";
import type { PermissionLevel, UploadResponse } from "../api/contracts";

interface FileUploadProps {
  onUpload: (file: File, level: PermissionLevel) => Promise<UploadResponse>;
  allowedLevels?: PermissionLevel[];
  onUploaded?: (response: UploadResponse) => void;
  trackProcessing?: boolean;
}
export function FileUpload({
  onUpload,
  onUploaded,
  trackProcessing = true,
  allowedLevels = [1],
}: FileUploadProps) {
  const titleId = useId();
  const inputId = useId();
  const levelId = useId();
  const [permissionLevel, setPermissionLevel] = useState<PermissionLevel>(1);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const alive = useRef(true);
  const inFlight = useRef(false);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  function selectFile(selected?: File) {
    setError("");
    setSuccess("");
    setFile(null);
    if (!selected) return;
    const reason = validateFile(selected);
    if (reason) setError(reason);
    else setFile(selected);
  }
  function drop(event: DragEvent) {
    event.preventDefault();
    setDragging(false);
    if (inFlight.current) return;
    if (event.dataTransfer.files.length > 1) {
      setFile(null);
      setSuccess("");
      setError("Please select one file at a time.");
      return;
    }
    selectFile(event.dataTransfer.files[0]);
  }
  async function upload() {
    if (!file || inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      const response = await onUpload(
        file,
        allowedLevels.includes(permissionLevel) ? permissionLevel : 1,
      );
      if (alive.current) {
        setSuccess(
          response.status === "indexed"
            ? `${response.filename} is indexed and ready to search. ${response.message ?? ""}`
            : `${response.filename} was received.${trackProcessing ? " Track its processing status below." : ""}`,
        );
        if (response.permission_level !== undefined)
          setSuccess(
            (value) => `${value} Access: Level ${response.permission_level}.`,
          );
        setFile(null);
        if (fileInput.current) fileInput.current.value = "";
        onUploaded?.(response);
      }
    } catch (reason) {
      if (alive.current)
        setError(
          reason instanceof Error
            ? reason.message
            : "Upload failed. Please try again.",
        );
    } finally {
      inFlight.current = false;
      if (alive.current) setBusy(false);
    }
  }
  return (
    <section className="upload-panel" aria-labelledby={titleId}>
      <div className="upload-intro">
        <span className="section-icon">
          <Icon name="upload" size={23} />
        </span>
        <div>
          <h2 id={titleId}>Add to your knowledge base</h2>
          <p>Upload a document with the appropriate access level.</p>
        </div>
      </div>
      <div
        className={`dropzone ${dragging ? "dragging" : ""} ${file ? "has-file" : ""}`}
        onDragOver={(event) => {
          event.preventDefault();
          if (!busy) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={drop}
      >
        <input
          ref={fileInput}
          className="sr-only"
          id={inputId}
          aria-label="Choose a document"
          type="file"
          accept=".pdf,.md,.txt"
          disabled={busy}
          onChange={(event) => {
            selectFile(event.target.files?.[0]);
            event.target.value = "";
          }}
        />
        <span className="dropzone-icon">
          <Icon name={file ? "file" : "upload"} size={26} />
        </span>
        <div className="dropzone-copy">
          <strong>{file ? file.name : "Drop your document here"}</strong>
          <span>
            {file
              ? `${fileSize(file.size)} · Ready to upload`
              : "PDF, Markdown, or TXT · Maximum 10 MB"}
          </span>
        </div>
        {file ? (
          <div className="file-actions">
            <button
              className="icon-button"
              aria-label="Remove selected file"
              disabled={busy}
              onClick={() => {
                setFile(null);
                setError("");
              }}
            >
              <Icon name="close" size={18} />
            </button>
            <button
              className="button primary"
              disabled={busy}
              onClick={() => void upload()}
            >
              {busy ? (
                <>
                  <span className="spinner" />
                  Uploading…
                </>
              ) : (
                <>
                  <Icon name="upload" size={17} />
                  Upload document
                </>
              )}
            </button>
          </div>
        ) : (
          <button
            className="button secondary"
            onClick={() => fileInput.current?.click()}
            disabled={busy}
          >
            Browse files
          </button>
        )}
      </div>
      <div className="permission-picker">
        <label htmlFor={levelId}>Document permission level</label>
        <select
          id={levelId}
          value={allowedLevels.includes(permissionLevel) ? permissionLevel : 1}
          disabled={busy}
          onChange={(event) =>
            setPermissionLevel(Number(event.target.value) as PermissionLevel)
          }
        >
          {allowedLevels.map((level) => (
            <option key={level} value={level}>
              Level {level} —{" "}
              {level === 1
                ? "General internal"
                : level === 2
                  ? "Restricted"
                  : "Highly restricted"}
            </option>
          ))}
        </select>
        <span>
          Default: Level 1.{" "}
          {allowedLevels.length === 1
            ? "Your account can upload Level 1 documents only."
            : "Levels 2 and 3 are visible to administrators only."}
        </span>
      </div>
      <div className="upload-policy">
        <Icon name="shield" size={15} />
        <span>
          Level 1 is available to all authenticated users. Access is verified by
          the server.
        </span>
      </div>
      {error && (
        <p className="notice error" role="alert">
          <Icon name="alert" size={18} />
          {error}
        </p>
      )}
      {success && (
        <p className="notice success" role="status">
          <Icon name="check" size={18} />
          {success}
        </p>
      )}
    </section>
  );
}
