import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { Icon } from "../components/Icon";
import { FileUpload } from "../components/FileUpload";
import { fileSize } from "../uploadPolicy";
import { SourceDrawer } from "../components/SourceDrawer";
import type { KnowledgeDocument, PreviewSelection } from "../types";

export function DocumentsPage() {
  const { session } = useAuth();
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState("");
  const [query, setQuery] = useState("");
  const [selection, setSelection] = useState<PreviewSelection | null>(null);
  const alive = useRef(true);
  const closePreview = useCallback(() => setSelection(null), []);
  const user = session!.user;
  const canUpload = user.permissions.includes("document:upload");
  const loadDocuments = useCallback(async () => {
    if (api.mode === "live") {
      setLoading(false);
      return;
    }
    try {
      const response = await api.documents(session!.access_token);
      if (alive.current) {
        setDocuments(response.documents);
        setListError("");
      }
    } catch (reason) {
      if (alive.current)
        setListError(
          reason instanceof Error
            ? reason.message
            : "Unable to load documents.",
        );
    } finally {
      if (alive.current) setLoading(false);
    }
  }, [session]);
  useEffect(() => {
    alive.current = true;
    void loadDocuments();
    return () => {
      alive.current = false;
    };
  }, [loadDocuments]);
  const processing = documents.some(
    (document) => document.status === "processing",
  );
  useEffect(() => {
    if (!processing) return;
    const interval = window.setInterval(() => void loadDocuments(), 1200);
    return () => window.clearInterval(interval);
  }, [processing, loadDocuments]);
  const filtered = documents.filter((document) =>
    document.filename.toLowerCase().includes(query.toLowerCase()),
  );
  const ready = documents.filter(
    (document) => document.status === "ready",
  ).length;
  return (
    <div className="documents-page">
      <header className="page-heading">
        <div>
          <h1>Document library</h1>
          <p>Your team’s knowledge, ready to explore.</p>
        </div>
        {api.mode === "mock" && (
          <span className="library-count">
            <Icon name="folder" size={17} />
            {documents.length} accessible documents
          </span>
        )}
      </header>
      {canUpload ? (
        <FileUpload
          onUpload={(file) => api.upload(file, session!.access_token)}
          onUploaded={() => {
            if (api.mode === "mock") void loadDocuments();
          }}
          trackProcessing={api.mode === "mock"}
        />
      ) : (
        <div className="read-only-note">
          <Icon name="shield" size={18} />
          <p>
            You have view-only access. Contact your administrator to request
            upload access.
          </p>
        </div>
      )}
      {api.mode === "mock" ? (
        <section className="library-section" aria-labelledby="library-title">
          <div className="library-toolbar">
            <div>
              <h2 id="library-title">
                Available documents<span>{documents.length}</span>
              </h2>
              <p>{ready} ready · Visible to your account</p>
            </div>
            <div className="search-field">
              <Icon name="search" size={18} />
              <label className="sr-only" htmlFor="document-search">
                Search documents by name
              </label>
              <input
                id="document-search"
                placeholder="Search documents…"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </div>
          </div>
          {listError && (
            <div className="notice error" role="alert">
              {listError}
              <button
                className="text-button"
                onClick={() => void loadDocuments()}
              >
                Retry
              </button>
            </div>
          )}
          <div className="document-table-wrap">
            <table className="document-table">
              <thead>
                <tr>
                  <th scope="col">Document</th>
                  <th scope="col">Department</th>
                  <th scope="col">Access</th>
                  <th scope="col">Status</th>
                  <th scope="col">Added</th>
                  <th scope="col">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((document) => (
                  <tr key={document.document_id}>
                    <td>
                      <div className="document-name">
                        <span
                          className={`file-symbol ${document.format === "Markdown" ? "markdown" : ""}`}
                        >
                          <Icon name="file" size={22} />
                        </span>
                        <div>
                          <strong>{document.filename}</strong>
                          <span>
                            {document.format} · {fileSize(document.size_bytes)}
                          </span>
                        </div>
                      </div>
                    </td>
                    <td>{document.department}</td>
                    <td>
                      <span className="access-tag">
                        Level {document.min_clearance}
                      </span>
                    </td>
                    <td>
                      <span className={`status ${document.status}`}>
                        {document.status === "ready" ? (
                          <Icon name="check" size={13} />
                        ) : document.status === "processing" ? (
                          <span className="spinner" />
                        ) : (
                          <Icon name="alert" size={13} />
                        )}
                        {document.status === "ready"
                          ? "Ready"
                          : document.status === "processing"
                            ? "Processing"
                            : "Failed"}
                      </span>
                    </td>
                    <td>
                      {new Date(document.uploaded_at).toLocaleDateString(
                        "en-US",
                        { month: "short", day: "numeric" },
                      )}
                    </td>
                    <td>
                      <button
                        className="icon-button"
                        aria-label={`Preview ${document.filename}`}
                        title="Preview document"
                        disabled={document.status !== "ready"}
                        onClick={() =>
                          setSelection({ documentId: document.document_id })
                        }
                      >
                        <Icon name="eye" size={19} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {loading && (
              <div className="loading-state" role="status">
                <span className="spinner" />
                Loading your documents…
              </div>
            )}
            {!loading && !listError && !filtered.length && (
              <div className="library-empty">
                <Icon name="search" size={28} />
                <h3>{query ? "No matching documents" : "No documents yet"}</h3>
                <p>
                  {query
                    ? "Try a different document name."
                    : "Uploaded documents will appear here."}
                </p>
                {query && (
                  <button className="text-button" onClick={() => setQuery("")}>
                    Clear search
                  </button>
                )}
              </div>
            )}
          </div>
          <div className="library-footer">
            <Icon name="shield" size={15} />
            Documents are filtered by your department and access level.
          </div>
        </section>
      ) : (
        <p className="notice" role="status">
          The document library is not available yet. You can still upload
          documents.
        </p>
      )}
      {selection && (
        <SourceDrawer selection={selection} onClose={closePreview} />
      )}
    </div>
  );
}
