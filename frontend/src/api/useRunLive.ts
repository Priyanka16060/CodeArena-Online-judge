import { useEffect, useRef, useState } from "react";
import { runLiveSocketUrl } from "./client";
import type { RunCaseEvent, RunFinalEvent } from "./types";

export type RunStatus = "idle" | "running" | "done" | "error";

interface RunState {
  status: RunStatus;
  cases: RunCaseEvent[];
  final: RunFinalEvent | null;
  errorMessage: string | null;
}

export function useRunLive(runId: string | null) {
  const [state, setState] = useState<RunState>({ status: "idle", cases: [], final: null, errorMessage: null });
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!runId) {
      setState({ status: "idle", cases: [], final: null, errorMessage: null });
      return;
    }

    setState({ status: "running", cases: [], final: null, errorMessage: null });
    const ws = new WebSocket(runLiveSocketUrl(runId));
    socketRef.current = ws;

    ws.onmessage = (event) => {
      let data: any;
      try {
        data = JSON.parse(event.data);
      } catch {
        return;
      }
      if (data.ping) return;

      if (data.final) {
        const finalEvent = data as RunFinalEvent;
        setState((s) => ({
          ...s,
          status: finalEvent.status === "error" ? "error" : "done",
          final: finalEvent,
          errorMessage: finalEvent.status === "error" ? finalEvent.message ?? "Run failed." : null,
        }));
        ws.close();
        return;
      }

      const caseEvent = data as RunCaseEvent;
      setState((s) => ({ ...s, cases: [...s.cases, caseEvent] }));
    };

    ws.onerror = () => {
      setState((s) => ({ ...s, status: "error", errorMessage: "Lost connection while running." }));
    };

    return () => {
      ws.close();
    };
  }, [runId]);

  return state;
}
