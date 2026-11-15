import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api/client";
import { citationLocation } from "../api/adapters";
import { useAuth } from "../context/AuthContext";
import type { PreviewSelection } from "../types";
import type { DocumentDetail } from "../api/contracts";
import { Icon } from "./Icon";

export function SourceDrawer({
  selection,
  onClose,
}: {
  selection: PreviewSelection;
  onClose: () => void;
}) {
  const { session } = useAuth();
  const [document, setDocument] = useState<DocumentDetail | null>(null);
  const [chunkContent, setChunkContent] = useState<string | null>(null);
  const [error, setError] = useState("");
  const panel = useRef<HTMLElement>(null);
  const close = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    let active = true;

    setDocument(null);
    setChunkContent(null);
    setError("");

    if (selection.citation?.unavailable) {
      setError("This source is unavailable or you no longer have access.");
      return;
    }

    const token = session!.access_token;
    const chunkId = selection.citation?.id;

    void Promise.all([
      api.document(selection.documentId, token),
      chunkId
        ? api.documentChunk(selection.documentId, chunkId, token)
        : Promise.resolve(null),
    ])
      .then(([documentValue, chunkValue]) => {
        if (!active) return;

        setDocument(documentValue);
        setChunkContent(chunkValue?.content ?? null);
      })
      .catch((reason) => {
        if (!active) return;

        setError(
          reason instanceof ApiError && [403, 404].includes(reason.status)
            ? "This source is unavailable or you no longer have access."
            : reason instanceof Error
              ? reason.message
              : "Unable to open the source.",
        );
      });

    return () => {
      active = false;
    };
  }, [
    selection.documentId,
    selection.citation?.id,
    selection.citation?.unavailable,
    session,
  ]);
  useEffect(() => {
    const previous = window.document.activeElement as HTMLElement | null;
    const originalOverflow = window.document.body.style.overflow;
    window.document.body.style.overflow = "hidden";
    close.current?.focus();
    function keydown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
      if (event.key === "Tab") {
        const elements = panel.current?.querySelectorAll<HTMLElement>(
          'button, a[href], [tabindex="0"]',
        );
        const first = elements?.[0];
        const last = elements?.[elements.length - 1];
        if (event.shiftKey && window.document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && window.document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
    }
    window.addEventListener("keydown", keydown);
    return () => {
      window.removeEventListener("keydown", keydown);
      window.document.body.style.overflow = originalOverflow;
      previous?.focus();
    };
  }, [onClose]);
  const citation = selection.citation;
  return (
    <div className="drawer-overlay" onClick={onClose}>
      <aside
        className="source-drawer"
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby="source-title"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="drawer-header">
          <div>
            <span className="eyebrow">SOURCE PREVIEW</span>
            <h2 id="source-title">
              {error
                ? "Unavailable source"
                : (document?.title ?? citation?.title ?? "Document source")}
            </h2>
          </div>
          <button
            className="icon-button"
            ref={close}
            onClick={onClose}
            aria-label="Close source preview"
          >
            <Icon name="close" />
          </button>
        </header>
        <div className="drawer-body">
          {!document && !error && (
            <div className="loading-state">
              <span className="spinner" />
              Loading source…
            </div>
          )}
          {error && (
            <p className="notice error" role="alert">
              {error}
            </p>
          )}
          {error && citation && <p>{citationLocation(citation)}</p>}
          {document && (
            <>
              <div className="source-meta">
                <span className="format-badge">{document.content_type}</span>
                <span>Level {document.permission_level}</span>
              </div>
              <dl className="detail-fields">
                <dt>Filename</dt>
                <dd>{document.filename}</dd>
                <dt>Creator</dt>
                <dd>{document.creator.display_name}</dd>
                <dt>Created</dt>
                <dd>{new Date(document.created_at).toLocaleString()}</dd>
                <dt>Updated</dt>
                <dd>{new Date(document.updated_at).toLocaleString()}</dd>
                <dt>Status</dt>
                <dd>{document.status}</dd>
                <dt>Available actions</dt>
                <dd>{document.available_actions.join(", ") || "None"}</dd>
              </dl>
              {citation && (
                <section className="evidence-block">
                  <div className="evidence-heading">
                    <Icon name="check" size={16} />
                    {citationLocation(citation)}
                    {citation.score !== undefined &&
                      ` · Score ${citation.score.toFixed(3)}`}
                  </div>
                  {chunkContent || citation.content ? (
                    <p>{chunkContent ?? citation.content}</p>
                  ) : (
                    <p>No source excerpt is available.</p>
                  )}
                </section>
              )}
              {document.preview && document.preview !== citation?.content ? (
                <section className="document-text" aria-label="Document text">
                  <div className="eyebrow">DOCUMENT EXCERPT</div>
                  <p>{document.preview}</p>
                </section>
              ) : (
                !document.preview &&
                  !chunkContent &&
                  !citation?.content && (
                    <p>No document excerpt is available.</p>
                  )
              )}
            </>
          )}
        </div>
        <footer className="drawer-footer">
          <Icon name="shield" size={16} />
          Only sources available to your account are shown.
        </footer>
      </aside>
    </div>
  );
}
