import { useEffect, useId, useRef, type ReactNode } from "react";

export function Dialog({
  title,
  children,
  onClose,
  busy = false,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  busy?: boolean;
}) {
  const titleId = useId();
  const panel = useRef<HTMLElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    panel.current?.focus();
    function keydown(event: KeyboardEvent) {
      if (event.key === "Escape" && !busy) onClose();
      if (event.key !== "Tab") return;
      const elements = panel.current?.querySelectorAll<HTMLElement>(
        "button:not(:disabled), select:not(:disabled), input:not(:disabled), a[href]",
      );
      if (!elements?.length) {
        event.preventDefault();
        return;
      }
      const first = elements[0],
        last = elements[elements.length - 1];
      if (
        event.shiftKey &&
        (document.activeElement === first ||
          document.activeElement === panel.current)
      ) {
        event.preventDefault();
        last.focus();
      } else if (
        !event.shiftKey &&
        (document.activeElement === last ||
          document.activeElement === panel.current)
      ) {
        event.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", keydown);
    return () => {
      document.removeEventListener("keydown", keydown);
      previous?.focus();
    };
  }, [busy, onClose]);
  return (
    <div className="drawer-overlay" onClick={() => !busy && onClose()}>
      <section
        ref={panel}
        tabIndex={-1}
        className="action-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(event) => event.stopPropagation()}
      >
        <h2 id={titleId}>{title}</h2>
        {children}
      </section>
    </div>
  );
}
