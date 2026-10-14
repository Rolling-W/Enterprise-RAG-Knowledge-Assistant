import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { citationLocation, toAssistantResponse } from "../api/adapters";
import { useAuth } from "../context/AuthContext";
import { Icon } from "../components/Icon";
import { SourceDrawer } from "../components/SourceDrawer";
import type { Message, PreviewSelection } from "../types";

const suggestions = [
  {
    title: "Time off & benefits",
    question: "How many days of annual leave do employees receive?",
    icon: "clock" as const,
  },
  {
    title: "Working remotely",
    question: "What is our remote work policy?",
    icon: "folder" as const,
  },
  {
    title: "Getting started",
    question: "What should I complete during my first week?",
    icon: "check" as const,
  },
];
export function AssistantPage() {
  const { session } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [selection, setSelection] = useState<PreviewSelection | null>(null);
  const [copied, setCopied] = useState("");
  const [copyError, setCopyError] = useState("");
  const requestNumber = useRef(0);
  const bottom = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const copyTimer = useRef<ReturnType<typeof setTimeout>>();
  const closePreview = useCallback(() => setSelection(null), []);
  useEffect(
    () => () => {
      requestNumber.current += 1;
      clearTimeout(copyTimer.current);
    },
    [],
  );
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, busy]);
  async function ask(value: string) {
    const query = value.trim();
    if (!query || busy || query.length > 500) return;
    const request = ++requestNumber.current;
    setMessages((previous) => [
      ...previous,
      { id: crypto.randomUUID(), kind: "user", content: query },
    ]);
    setQuestion("");
    setBusy(true);
    try {
      const response = toAssistantResponse(
        await api.search(query, session!.access_token),
      );
      if (request === requestNumber.current)
        setMessages((previous) => [
          ...previous,
          {
            id: response.request_id,
            kind: "assistant",
            content: response.answer,
            citations: response.citations,
          },
        ]);
    } catch (reason) {
      if (request === requestNumber.current)
        setMessages((previous) => [
          ...previous,
          {
            id: crypto.randomUUID(),
            kind: "assistant",
            failed: true,
            content:
              reason instanceof Error
                ? reason.message
                : "Unable to get an answer. Please try again.",
          },
        ]);
    } finally {
      if (request === requestNumber.current) {
        setBusy(false);
        input.current?.focus();
      }
    }
  }
  function submit(event: FormEvent) {
    event.preventDefault();
    void ask(question);
  }
  function keydown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing
    ) {
      event.preventDefault();
      void ask(question);
    }
  }
  function newConversation() {
    requestNumber.current += 1;
    setMessages([]);
    setQuestion("");
    setBusy(false);
    setSelection(null);
    setCopyError("");
    input.current?.focus();
  }
  async function copy(message: Message) {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(message.id);
      setCopyError("");
      clearTimeout(copyTimer.current);
      copyTimer.current = setTimeout(() => setCopied(""), 2000);
    } catch {
      setCopyError(
        "Clipboard access is unavailable. Select the answer text to copy it.",
      );
    }
  }
  return (
    <div className="assistant-page">
      <header className="page-heading">
        <div>
          <h1>Knowledge assistant</h1>
          <p>Ask a question. Find an answer backed by your documents.</p>
        </div>
        <button className="button secondary" onClick={newConversation}>
          <Icon name="plus" size={17} />
          New conversation
        </button>
      </header>
      <div className="assistant-scope">
        <span>
          <Icon name="shield" size={15} />
          {session!.user.role === "Executive"
            ? "Cross-department access"
            : "Your department & shared knowledge"}
        </span>
        <Link to="/documents">
          Browse documents
          <Icon name="chevron" size={14} />
        </Link>
      </div>
      <div
        className={`conversation ${messages.length === 0 ? "is-empty" : ""}`}
        role="log"
        aria-label="Conversation"
        aria-live="polite"
      >
        {messages.length === 0 ? (
          <section className="assistant-welcome">
            <div className="welcome-symbol">
              <Icon name="sparkles" size={34} />
            </div>
            <span className="eyebrow">LESS SEARCHING. MORE CLARITY.</span>
            <h2>What would you like to know?</h2>
            <p>
              Explore policies, find guidance, and get answers
              <br className="desktop-break" /> with sources you can verify.
            </p>
            <div className="suggestion-grid">
              {suggestions.map((item) => (
                <button
                  className="suggestion"
                  key={item.title}
                  onClick={() => void ask(item.question)}
                >
                  <span className="suggestion-icon">
                    <Icon name={item.icon} size={20} />
                  </span>
                  <strong>{item.title}</strong>
                  <span>{item.question}</span>
                  <Icon name="chevron" className="suggestion-arrow" size={16} />
                </button>
              ))}
            </div>
          </section>
        ) : (
          <div className="message-list">
            {messages.map((message) => (
              <article
                key={message.id}
                className={`message ${message.kind} ${message.failed ? "message-error" : ""}`}
              >
                <div className="message-avatar">
                  {message.kind === "assistant" ? (
                    <Icon name="sparkles" size={21} />
                  ) : (
                    session!.user.name
                      .split(" ")
                      .map((part) => part[0])
                      .join("")
                  )}
                </div>
                <div className="message-body">
                  <div className="message-label">
                    {message.kind === "assistant"
                      ? "Knowledge assistant"
                      : "You"}
                  </div>
                  <div className="answer-text">
                    {message.content.split("\n\n").map((paragraph, index) => (
                      <p key={index}>{paragraph}</p>
                    ))}
                  </div>
                  {!!message.citations?.length && (
                    <div className="citations">
                      <div className="citations-label">
                        SOURCES · {message.citations.length}
                      </div>
                      {message.citations.map((citation, index) => (
                        <button
                          className="citation-card"
                          key={citation.id}
                          onClick={() =>
                            setSelection({
                              documentId: citation.document_id,
                              citation,
                            })
                          }
                        >
                          <span className="citation-number">{index + 1}</span>
                          <div>
                            <strong>{citation.title}</strong>
                            <span>{citationLocation(citation)}</span>
                          </div>
                          <Icon name="chevron" size={16} />
                        </button>
                      ))}
                    </div>
                  )}
                  {message.kind === "assistant" && !message.failed && (
                    <div className="answer-actions">
                      <button onClick={() => void copy(message)}>
                        <Icon
                          name={copied === message.id ? "check" : "copy"}
                          size={15}
                        />
                        {copied === message.id ? "Copied" : "Copy answer"}
                      </button>
                      {!!message.citations?.length && (
                        <span>
                          <Icon name="check" size={14} />
                          Retrieved excerpts
                        </span>
                      )}
                    </div>
                  )}
                  {message.failed && (
                    <button
                      className="text-button"
                      onClick={() => {
                        const position = messages.findIndex(
                          (item) => item.id === message.id,
                        );
                        const previous = messages[position - 1];
                        if (previous) void ask(previous.content);
                      }}
                      disabled={busy}
                    >
                      Try again
                    </button>
                  )}
                </div>
              </article>
            ))}
            {busy && (
              <div className="message assistant">
                <div className="message-avatar">
                  <Icon name="sparkles" size={21} />
                </div>
                <div className="thinking" role="status">
                  <span />
                  <span />
                  <span />
                  Finding supporting sources…
                </div>
              </div>
            )}
            <div ref={bottom} />
          </div>
        )}
      </div>
      <div className="composer-area">
        {copyError && (
          <p className="notice error" role="alert">
            {copyError}
          </p>
        )}
        <form className="composer" onSubmit={submit}>
          <label className="sr-only" htmlFor="question">
            Ask a question about your documents
          </label>
          <textarea
            id="question"
            ref={input}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={keydown}
            placeholder="Ask a question about your documents…"
            rows={2}
            maxLength={500}
            disabled={busy}
          />
          <div className="composer-toolbar">
            <span>Enter to send · Shift + Enter for a new line</span>
            <div>
              <span className="character-count">{question.length}/500</span>
              <button
                className="send-button"
                type="submit"
                disabled={!question.trim() || busy}
                aria-label="Send question"
              >
                {busy ? (
                  <span className="spinner" />
                ) : (
                  <Icon name="arrow" size={20} />
                )}
              </button>
            </div>
          </div>
        </form>
        <p className="composer-note">
          Review the sources to verify important details.
        </p>
      </div>
      {selection && (
        <SourceDrawer selection={selection} onClose={closePreview} />
      )}
    </div>
  );
}
