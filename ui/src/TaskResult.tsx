import { useEffect, useState } from "react";

export type TaskRunView = {
  run_id: string; dispatch_status: string; request_id: string | null;
  lifecycle: string | null; result_status: string | null; provider_started: boolean | null;
  delivery: string; clock_quality: string;
};

export function TaskResult({ run }: { run?: TaskRunView | null }) {
  const [response, setResponse] = useState("");
  const [error, setError] = useState("");
  const requestId = run?.request_id;
  const resultStatus = run?.result_status;
  useEffect(() => {
    setResponse(""); setError("");
    if (!requestId) return;
    const controller = new AbortController();
    let timer: number | undefined;
    let attempts = 0;
    // Terminal metadata can precede the ephemeral live-result subscriber.
    // Only retry this exact current result, at most 15 reads over 28 seconds.
    // Nothing here reclaims a task or restarts a provider/action.
    const read = async () => {
      attempts += 1;
      try {
        const value = await fetch(`/api/v1/conversation/${encodeURIComponent(requestId)}`, {
          credentials: "same-origin", cache: "no-store", signal: controller.signal,
          headers: { Accept: "application/json" },
        });
        if (!value.ok) {
          setError("Current result unavailable for this session.");
          return; // Authentication/scope failure must not keep probing.
        }
        const result = await value.json() as { response?: string | null; detail?: string | null };
        if (controller.signal.aborted) return;
        setResponse(result.response ?? result.detail ?? "Live result unavailable.");
        setError("");
        if (!result.response && attempts < 15) timer = window.setTimeout(() => { void read(); }, 2000);
      } catch (reason) {
        if (controller.signal.aborted) return;
        setError(reason instanceof Error ? reason.message : "Live result unavailable.");
        if (attempts < 15) timer = window.setTimeout(() => { void read(); }, 2000);
      }
    };
    void read();
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [requestId, resultStatus]);
  if (!run) return null;
  return <span className="stack" aria-live="polite">
    <small className="muted">Dispatch: {run.dispatch_status.replaceAll("_", " ")} · Result: {(run.result_status ?? run.lifecycle ?? "PENDING").replaceAll("_", " ")}</small>
    <small className="muted">Delivery: {run.delivery.replaceAll("_", " ").toLowerCase()}</small>
    {run.clock_quality === "FUTURE_DATED_HISTORICAL_RECORD" && <small>Historical clock quality unavailable; not current activity.</small>}
    {response && <small>{response}</small>}{error && <small role="status">{error}</small>}
  </span>;
}
