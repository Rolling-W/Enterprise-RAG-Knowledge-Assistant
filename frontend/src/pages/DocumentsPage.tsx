import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api/client";
import { productRole } from "../api/adapters";
import { useAuth } from "../context/AuthContext";
import { FileUpload } from "../components/FileUpload";
import { SourceDrawer } from "../components/SourceDrawer";
import { Dialog } from "../components/Dialog";
import { fileSize } from "../uploadPolicy";
import type {
  DocumentAction,
  DocumentQuery,
  DocumentSummary,
  PermissionLevel,
  PaginatedDocuments,
} from "../api/contracts";
import type { PreviewSelection } from "../types";

const emptyPage: PaginatedDocuments = {
  items: [],
  total: 0,
  page: 1,
  page_size: 20,
};
export function DocumentsPage() {
  const { session } = useAuth();
  const token = session!.access_token;
  const role = productRole(session!.user.role);
  const [data, setData] = useState(emptyPage);
  const [params, setParams] = useState<DocumentQuery>({
    page: 1,
    page_size: 20,
    sort_by: "updated_at",
    sort_order: "desc",
    q: "",
  });
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [revision, setRevision] = useState(0);
  const [selection, setSelection] = useState<PreviewSelection | null>(null);
  const [operation, setOperation] = useState<{
    document: DocumentSummary;
    action: DocumentAction;
  } | null>(null);
  const [level, setLevel] = useState<PermissionLevel>(1);
  const [saving, setSaving] = useState(false);
  const [operationError, setOperationError] = useState("");
  const inFlight = useRef(false);
  const requestId = useRef(0);
  const closePreview = useCallback(() => setSelection(null), []);
  const closeOperation = useCallback(() => setOperation(null), []);
  const refresh = () => setRevision((value) => value + 1);
  useEffect(() => {
    const timer = window.setTimeout(
      () =>
        setParams((current) =>
          current.q === query.trim()
            ? current
            : { ...current, q: query.trim(), page: 1 },
        ),
      250,
    );
    return () => window.clearTimeout(timer);
  }, [query]);
  useEffect(() => {
    const request = ++requestId.current;
    setLoading(true);
    setError("");
    void api
      .documents(token, params)
      .then((response) => {
        if (request !== requestId.current) return;
        const lastPage = Math.max(
          1,
          Math.ceil(response.total / response.page_size),
        );
        if ((params.page ?? 1) > lastPage)
          setParams((current) => ({ ...current, page: lastPage }));
        else setData(response);
      })
      .catch((reason) => {
        if (request !== requestId.current) return;
        setData(emptyPage);
        setError(
          reason instanceof ApiError && [404, 405, 501].includes(reason.status)
            ? "Document management is not available on this backend yet. Upload and search remain available."
            : reason instanceof Error
              ? reason.message
              : "Unable to load documents.",
        );
      })
      .finally(() => {
        if (request === requestId.current) setLoading(false);
      });
    return () => {
      requestId.current += 1;
    };
  }, [token, params, revision]);
  const processing = data.items.some((document) =>
    ["processing", "deleting"].includes(document.status),
  );
  useEffect(() => {
    if (!processing || error) return;
    const timer = window.setInterval(
      () => setRevision((value) => value + 1),
      2000,
    );
    return () => window.clearInterval(timer);
  }, [processing, error]);
  function filter<K extends keyof DocumentQuery>(
    key: K,
    value: DocumentQuery[K],
  ) {
    setParams((current) => ({ ...current, [key]: value, page: 1 }));
  }
  async function perform() {
    if (!operation || inFlight.current) return;
    inFlight.current = true;
    setSaving(true);
    setOperationError("");
    const { document, action } = operation;
    try {
      if (action === "delete")
        await api.deleteDocument(document.document_id, token);
      if (action === "reindex")
        await api.reindexDocument(document.document_id, token);
      if (action === "change_permission")
        await api.changePermission(document.document_id, level, token);
      setNotice(
        action === "delete"
          ? "Document deleted."
          : action === "reindex"
            ? "Re-indexing started."
            : "Document permission updated.",
      );
      setOperation(null);
      setSelection(null);
      refresh();
    } catch (reason) {
      setOperationError(
        reason instanceof Error
          ? reason.message
          : "The operation failed. Please retry.",
      );
      refresh();
    } finally {
      inFlight.current = false;
      setSaving(false);
    }
  }
  return (
    <div className="documents-page">
      <header className="page-heading">
        <div>
          <h1>Document library</h1>
          <p>Find and manage the documents available to your account.</p>
        </div>
        <span>{data.total} accessible documents</span>
      </header>
      {session!.user.permissions.includes("document:upload") ? (
        <FileUpload
          allowedLevels={role === "admin" ? [1, 2, 3] : [1]}
          onUpload={(file, permissionLevel) =>
            api.upload(file, token, permissionLevel)
          }
          onUploaded={refresh}
          trackProcessing
        />
      ) : (
        <p className="read-only-note">
          You have view-only access. Contact your administrator to request
          upload access.
        </p>
      )}
      <section className="library-section" aria-labelledby="library-title">
        <div className="library-toolbar">
          <h2 id="library-title">Available documents</h2>
          <button
            className="button secondary"
            onClick={refresh}
            disabled={loading}
          >
            Refresh documents
          </button>
        </div>
        <div className="document-filters">
          <label>
            Search documents by name
            <input
              placeholder="Title, filename, tags or keywords"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <label>
            Permission level
            <select
              value={params.permission_level ?? ""}
              onChange={(event) =>
                filter(
                  "permission_level",
                  event.target.value
                    ? (Number(event.target.value) as PermissionLevel)
                    : undefined,
                )
              }
            >
              <option value="">All permitted levels</option>
              {(role === "admin" ? [1, 2, 3] : [1]).map((item) => (
                <option key={item} value={item}>
                  Level {item}
                </option>
              ))}
            </select>
          </label>
          <label>
            Status
            <select
              value={params.status ?? ""}
              onChange={(event) =>
                filter(
                  "status",
                  (event.target.value as DocumentQuery["status"]) || undefined,
                )
              }
            >
              <option value="">All statuses</option>
              {["processing", "indexed", "failed", "deleting"].map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <label>
            Creator ID
            <input
              value={params.creator_id ?? ""}
              placeholder="Filter by creator ID"
              onChange={(event) => filter("creator_id", event.target.value)}
            />
          </label>
          <label>
            Sort by
            <select
              value={params.sort_by}
              onChange={(event) =>
                filter(
                  "sort_by",
                  event.target.value as DocumentQuery["sort_by"],
                )
              }
            >
              {[
                "updated_at",
                "created_at",
                "filename",
                "permission_level",
                "status",
              ].map((item) => (
                <option key={item} value={item}>
                  {item.split("_").join(" ")}
                </option>
              ))}
            </select>
          </label>
          <label>
            Sort order
            <select
              value={params.sort_order}
              onChange={(event) =>
                filter("sort_order", event.target.value as "asc" | "desc")
              }
            >
              <option value="desc">Descending</option>
              <option value="asc">Ascending</option>
            </select>
          </label>
        </div>
        {notice && (
          <p className="notice" role="status">
            {notice}
          </p>
        )}
        {error && (
          <p className="notice error" role="alert">
            {error}{" "}
            <button className="text-button" onClick={refresh}>
              Retry
            </button>
          </p>
        )}
        {loading && (
          <p className="loading-state" role="status">
            Loading your documents…
          </p>
        )}
        <div className="document-table-wrap" aria-busy={loading}>
          <table className="document-table">
            <thead>
              <tr>
                <th scope="col">Document</th>
                <th scope="col">Creator</th>
                <th scope="col">Access</th>
                <th scope="col">Status</th>
                <th scope="col">Updated</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((document) => (
                <tr key={document.document_id}>
                  <td>
                    <strong>{document.title || document.filename}</strong>
                    <div className="document-secondary">
                      {document.title !== document.filename
                        ? document.filename + " · "
                        : ""}
                      {fileSize(document.size_bytes)}
                    </div>
                  </td>
                  <td title={document.creator.user_id}>
                    {document.creator.display_name}
                  </td>
                  <td>
                    <span className="access-tag">
                      Level {document.permission_level}
                    </span>
                  </td>
                  <td>
                    <span
                      className={
                        "status " +
                        (document.status === "indexed"
                          ? "ready"
                          : document.status)
                      }
                    >
                      {document.status === "indexed"
                        ? "Ready"
                        : document.status}
                    </span>
                  </td>
                  <td>{new Date(document.updated_at).toLocaleString()}</td>
                  <td>
                    <div className="row-actions">
                      {document.available_actions.map((action) => {
                        const label =
                          action === "read"
                            ? "Details"
                            : action === "change_permission"
                              ? "Change permission"
                              : action === "reindex"
                                ? "Re-index"
                                : "Delete";
                        return (
                          <button
                            key={action}
                            className="text-button"
                            disabled={saving || loading}
                            aria-label={label + " " + document.filename}
                            onClick={() => {
                              if (action === "read")
                                setSelection({
                                  documentId: document.document_id,
                                });
                              else {
                                setOperation({ document, action });
                                setLevel(document.permission_level);
                                setOperationError("");
                              }
                            }}
                          >
                            {label}
                          </button>
                        );
                      })}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!loading && !error && !data.items.length && (
          <div className="library-empty">
            <h3>
              {query ||
              params.creator_id ||
              params.status ||
              params.permission_level
                ? "No matching documents"
                : "No documents yet"}
            </h3>
            <p>Try changing your filters or upload a document.</p>
          </div>
        )}
        <div className="pagination">
          <button
            className="button secondary"
            disabled={loading || (params.page ?? 1) <= 1}
            onClick={() =>
              setParams((current) => ({
                ...current,
                page: (current.page ?? 1) - 1,
              }))
            }
          >
            Previous page
          </button>
          <span>
            Page {params.page ?? 1} of{" "}
            {Math.max(1, Math.ceil(data.total / (params.page_size ?? 20)))}
          </span>
          <button
            className="button secondary"
            disabled={
              loading ||
              (params.page ?? 1) * (params.page_size ?? 20) >= data.total
            }
            onClick={() =>
              setParams((current) => ({
                ...current,
                page: (current.page ?? 1) + 1,
              }))
            }
          >
            Next page
          </button>
          <label>
            Per page
            <select
              value={params.page_size}
              onChange={(event) =>
                filter("page_size", Number(event.target.value))
              }
            >
              {[10, 20, 50].map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </label>
        </div>
      </section>
      {selection && (
        <SourceDrawer selection={selection} onClose={closePreview} />
      )}
      {operation && (
        <Dialog
          title={
            operation.action === "delete"
              ? "Delete document?"
              : operation.action === "reindex"
                ? "Re-index document?"
                : "Change document permission"
          }
          onClose={closeOperation}
          busy={saving}
        >
          <p>{operation.document.filename}</p>
          {operation.action === "delete" ? (
            <p>
              This removes the document and its search index. Saved citations
              may become unavailable.
            </p>
          ) : operation.action === "change_permission" ? (
            <label>
              New permission level
              <select
                value={level}
                disabled={saving}
                onChange={(event) =>
                  setLevel(Number(event.target.value) as PermissionLevel)
                }
              >
                {[1, 2, 3].map((item) => (
                  <option key={item} value={item}>
                    Level {item}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <p>
              The document will be processed again using its current permission
              level.
            </p>
          )}
          {operationError && (
            <p className="notice error" role="alert">
              {operationError}
            </p>
          )}
          <div className="dialog-actions">
            <button
              className="button secondary"
              disabled={saving}
              onClick={closeOperation}
            >
              Cancel
            </button>
            <button
              className="button primary"
              disabled={saving}
              onClick={() => void perform()}
            >
              {saving ? "Saving…" : "Confirm"}
            </button>
          </div>
        </Dialog>
      )}
    </div>
  );
}
