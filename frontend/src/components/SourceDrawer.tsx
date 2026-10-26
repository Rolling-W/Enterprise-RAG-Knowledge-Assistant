import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { citationLocation } from "../api/adapters";
import { useAuth } from "../context/AuthContext";
import type { KnowledgeDocument, PreviewSelection } from "../types";
import { Icon } from "./Icon";

export function SourceDrawer({
  selection,
  onClose,
}: {
  selection: PreviewSelection;
  onClose: () => void;
}) {
  const { session } = useAuth();
  const [document, setDocument] = useState<KnowledgeDocument | null>(null);
  const [error, setError] = useState("");
  const panel = useRef<HTMLElement>(null);
  const close = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    let active = true;
    setDocument(null);
    setError("");
    if (api.mode === "live") return;
    void api
      .document(selection.documentId, session!.access_token)
      .then((value) => {
        if (active) setDocument(value);
      })
      .catch((reason) => {
        if (active)
          setError(
            reason instanceof Error
              ? reason.message
              : "Unable to open the source.",
          );
      });
    return () => {
      active = false;
    };
  }, [selection.documentId, session]);
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
              {document?.filename ?? citation?.title ?? "Document source"}
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
          {!document && !error && api.mode === "mock" && (
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
          {api.mode === "live" && citation && (
            <section className="evidence-block">
              <div className="evidence-heading">
                {citationLocation(citation)} · Score {citation.score.toFixed(3)}
              </div>
              <p>{citation.content}</p>
            </section>
          )}
          {document && (
            <>
              <div className="source-meta">
                <span className="format-badge">{document.format}</span>
                <span>{document.department}</span>
                <span>Level {document.min_clearance}</span>
              </div>
              {citation && (
                <section className="evidence-block">
                  <div className="evidence-heading">
                    <Icon name="check" size={16} />
                    {citationLocation(citation)} · Score {citation.score.toFixed(3)}
                  </div>
                  <p>{citation.content}</p>
                </section>
              )}
              <section className="document-text" aria-label="Document text">
                <div className="eyebrow">DOCUMENT EXCERPT</div>
                <p>{document.preview}</p>
              </section>
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
