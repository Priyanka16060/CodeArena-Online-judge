import { useEffect, useRef, useState } from "react";
import { fetchSubmission, submissionLiveSocketUrl } from "./client";
import type { SubmissionResult, Verdict } from "./types";

export type LiveStatus = "idle" | "connecting" | "pending" | "done" | "error";

interface LiveState {
  status: LiveStatus;
  liveVerdict: Verdict | null;
  result: SubmissionResult | null;
  errorMessage: string | null;
}

/**
 * Opens /submissions/{id}/live, tracks the streamed verdict, and once the
 * worker reports `final: true`, fetches the full SubmissionOut over REST so
 * we can show timing/memory/stderr the WebSocket payload doesn't carry.
 */
export function useSubmissionLive(submissionId: string | null) {
  const [state, setState] = useState<LiveState>({
    status: "idle",
    liveVerdict: null,
    result: null,
    errorMessage: null,
  });
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!submissionId) {
      setState({ status: "idle", liveVerdict: null, result: null, errorMessage: null });
      return;
    }

    setState({ status: "connecting", liveVerdict: null, result: null, errorMessage: null });

    const ws = new WebSocket(submissionLiveSocketUrl(submissionId));
    socketRef.current = ws;

    ws.onmessage = async (event) => {
      let data: any;
      try {
        data = JSON.parse(event.data);
      } catch {
        return;
      }

      if (data.error) {
        setState((s) => ({ ...s, status: "error", errorMessage: data.error }));
        return;
      }
      if (data.ping) return;

      if (data.verdict) {
        setState((s) => ({ ...s, status: "pending", liveVerdict: data.verdict }));
      }

      if (data.final) {
        try {
          const full = await fetchSubmission(submissionId);
          setState({ status: "done", liveVerdict: full.verdict, result: full, errorMessage: null });
        } catch {
          setState((s) => ({ ...s, status: "done" }));
        }
        ws.close();
      }
    };

    ws.onerror = () => {
      setState((s) => ({ ...s, status: "error", errorMessage: "Lost connection to the judge." }));
    };

    return () => {
      ws.close();
    };
  }, [submissionId]);

  return state;
}
