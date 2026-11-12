import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api/client";
import type { ConversationSummary, Page } from "../api/contracts";
import { Dialog } from "./Dialog";

export function ConversationHistory({
  token,
  activeId,
  revision,
  onSelect,
  onDeleted,
}: {
  token: string;
  activeId: string | null;
  revision: number;
  onSelect: (id: string) => void;
  onDeleted: (id: string) => void;
}) {
  const [data, setData] = useState<Page<ConversationSummary>>({
    items: [],
    page: 1,
    page_size: 20,
    total: 0,
  });
  const [page, setPage] = useState(1);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [target, setTarget] = useState<ConversationSummary | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const inFlight = useRef(false);
  const close = useCallback(() => setTarget(null), []);
  useEffect(() => setPage(1), [revision]);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    void api
      .conversations(token, page)
      .then((response) => {
        if (!active) return;
        const lastPage = Math.max(
          1,
          Math.ceil(response.total / response.page_size),
        );
        if (page > lastPage) setPage(lastPage);
        else setData(response);
      })
      .catch((reason) => {
        if (!active) return;
        setData({ items: [], page, page_size: 20, total: 0 });
        setError(
          reason instanceof ApiError && [404, 405, 501].includes(reason.status)
            ? "Conversation history is not available on this backend yet."
            : reason instanceof Error
              ? reason.message
              : "Unable to load conversation history.",
        );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [token, page, revision, refresh]);
  async function remove() {
    if (!target || inFlight.current) return;
    inFlight.current = true;
    setDeleting(true);
    setDeleteError("");
    try {
      await api.deleteConversation(target.conversation_id, token);
      onDeleted(target.conversation_id);
      setTarget(null);
      setRefresh((value) => value + 1);
    } catch (reason) {
      setDeleteError(
        reason instanceof Error
          ? reason.message
          : "Unable to delete conversation.",
      );
    } finally {
      inFlight.current = false;
      setDeleting(false);
    }
  }
  return (
    <details className="conversation-history" open>
      <summary>Conversation history</summary>
      <div className="history-toolbar">
        <span>Only your saved conversations</span>
        <button
          className="text-button"
          disabled={loading}
          onClick={() => setRefresh((value) => value + 1)}
        >
          Refresh history
        </button>
      </div>
      {loading && <p role="status">Loading history…</p>}
      {error && (
        <p className="notice" role="status">
          {error}
        </p>
      )}
      {!loading && !error && !data.items.length && (
        <p>No saved conversations yet.</p>
      )}
      <ul className="history-list">
        {data.items.map((conversation) => (
          <li key={conversation.conversation_id}>
            <button
              className="history-item"
              aria-current={
                conversation.conversation_id === activeId ? "true" : undefined
              }
              onClick={() => onSelect(conversation.conversation_id)}
            >
              <strong>{conversation.title || "Untitled conversation"}</strong>
              <time dateTime={conversation.updated_at}>
                {new Date(conversation.updated_at).toLocaleString()}
              </time>
            </button>
            <button
              className="text-button"
              aria-label={`Delete conversation ${conversation.title || "Untitled conversation"}`}
              onClick={() => {
                setTarget(conversation);
                setDeleteError("");
              }}
            >
              Delete
            </button>
          </li>
        ))}
      </ul>
      {data.total > data.page_size && (
        <div className="pagination">
          <button
            disabled={loading || page === 1}
            onClick={() => setPage((value) => value - 1)}
          >
            Previous history page
          </button>
          <span>Page {page}</span>
          <button
            disabled={loading || page * data.page_size >= data.total}
            onClick={() => setPage((value) => value + 1)}
          >
            Next history page
          </button>
        </div>
      )}
      {target && (
        <Dialog title="Delete conversation?" onClose={close} busy={deleting}>
          <p>{target.title || "Untitled conversation"}</p>
          <p>This removes the saved conversation and its messages.</p>
          {deleteError && (
            <p className="notice error" role="alert">
              {deleteError}
            </p>
          )}
          <div className="dialog-actions">
            <button
              className="button secondary"
              disabled={deleting}
              onClick={close}
            >
              Cancel
            </button>
            <button
              className="button primary"
              disabled={deleting}
              onClick={() => void remove()}
            >
              {deleting ? "Deleting…" : "Confirm"}
            </button>
          </div>
        </Dialog>
      )}
    </details>
  );
}
