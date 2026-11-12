import { useRef, useState } from "react";
import { api } from "../api/client";
import type { ScoringDebugResponse, SearchMode } from "../api/contracts";

const score = (value: number | null) =>
  value === null
    ? "—"
    : value.toLocaleString(undefined, { maximumFractionDigits: 6 });
const scoreKeys = [
  "bm25_raw",
  "bm25_rank",
  "dense_raw",
  "dense_rank",
  "fusion",
  "rerank",
  "final",
] as const;
export function ScoringDebug({ token }: { token: string }) {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<SearchMode>("hybrid");
  const [topK, setTopK] = useState(5);
  const [limit, setLimit] = useState(20);
  const [result, setResult] = useState<ScoringDebugResponse | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const inFlight = useRef(false);
  return (
    <details className="scoring-debug">
      <summary>Scoring diagnostics (development)</summary>
      {api.mode === "mock" && (
        <p className="notice">Demo scores and timings are simulated.</p>
      )}
      <form
        className="debug-controls"
        onSubmit={async (event) => {
          event.preventDefault();
          if (inFlight.current || !query.trim()) return;
          inFlight.current = true;
          setBusy(true);
          setError("");
          setResult(null);
          try {
            setResult(
              await api.debugSearch(
                {
                  query: query.trim(),
                  search_mode: mode,
                  top_k: topK,
                  candidate_limit: limit,
                },
                token,
              ),
            );
          } catch (reason) {
            setError(
              reason instanceof Error
                ? reason.message
                : "Unable to load scoring diagnostics.",
            );
          } finally {
            inFlight.current = false;
            setBusy(false);
          }
        }}
      >
        <label>
          Debug query
          <input
            required
            maxLength={500}
            value={query}
            disabled={busy}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <label>
          Debug search mode
          <select
            value={mode}
            disabled={busy}
            onChange={(event) => setMode(event.target.value as SearchMode)}
          >
            {["hybrid", "semantic", "keyword"].map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
        </label>
        <label>
          Top-k
          <input
            type="number"
            min={1}
            max={20}
            value={topK}
            disabled={busy}
            onChange={(event) => setTopK(Number(event.target.value))}
          />
        </label>
        <label>
          Candidate limit
          <input
            type="number"
            min={1}
            max={100}
            value={limit}
            disabled={busy}
            onChange={(event) => setLimit(Number(event.target.value))}
          />
        </label>
        <button className="button secondary" disabled={busy || !query.trim()}>
          {busy ? "Inspecting…" : "Inspect scoring"}
        </button>
      </form>
      {error && (
        <p className="notice error" role="alert">
          {error}
        </p>
      )}
      {result && (
        <div className="debug-results">
          <p>
            Query: {result.query} · Mode: {result.search_mode} · Top-k:{" "}
            {result.top_k} · Stages: {result.stages.join(", ")}
          </p>
          <p>Request: {result.request_id}</p>
          <p>
            — means this stage was not used. Highlighted rows are in the final
            top-k.
          </p>
          <div className="document-table-wrap">
            <table className="document-table">
              <caption>Candidate scores and final ranking</caption>
              <thead>
                <tr>
                  {[
                    "Rank",
                    "Document / chunk",
                    "Level",
                    "BM25 raw",
                    "BM25 rank",
                    "Dense raw",
                    "Dense rank",
                    "Fusion",
                    "Rerank",
                    "Final",
                  ].map((label) => (
                    <th key={label} scope="col">
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[...result.candidates]
                  .sort((a, b) => a.final_rank - b.final_rank)
                  .map((item) => (
                    <tr
                      className={
                        item.final_rank <= result.top_k ? "top-result" : ""
                      }
                      key={item.document_id + ":" + item.chunk_id}
                    >
                      <td>{item.final_rank}</td>
                      <td>
                        {item.document_id}
                        <br />
                        {item.chunk_id}
                      </td>
                      <td>{item.permission_level}</td>
                      {scoreKeys.map((key) => (
                        <td key={key}>{score(item.scores[key])}</td>
                      ))}
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
          {!result.candidates.length && (
            <p>No authorized candidates matched this query.</p>
          )}
          <dl className="timing-list">
            {Object.entries(result.timings_ms).map(([stage, elapsed]) => (
              <div key={stage}>
                <dt>{stage}</dt>
                <dd>{elapsed.toFixed(2)} ms</dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </details>
  );
}
