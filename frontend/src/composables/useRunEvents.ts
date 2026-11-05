import { onScopeDispose, ref, type Ref } from "vue";

import { getAuthToken } from "../api/client";
import { createSseParser, type SseEvent } from "../api/sse";
import type { RunReport } from "../api/types";
import { getRunReport } from "../api/runs";

export type ConnectionState = "idle" | "connecting" | "open" | "reconnecting" | "polling" | "closed";

export interface RunEventState {
  events: Ref<SseEvent[]>;
  connectionState: Ref<ConnectionState>;
  start: (after?: string) => Promise<void>;
  stop: () => void;
}

interface Options {
  onFinished?: (report: RunReport) => void;
  onUnauthorized?: () => void;
  fetchImpl?: typeof fetch;
  pollIntervalMs?: number;
  maxReconnectFailures?: number;
}

const TERMINAL = new Set(["passed", "failed", "error", "interrupted"]);

export function useRunEvents(runId: string, options: Options = {}): RunEventState {
  const events = ref<SseEvent[]>([]);
  const connectionState = ref<ConnectionState>("idle");
  const seen = new Set<string>();
  const fetchImpl = options.fetchImpl ?? fetch;
  const maxFailures = options.maxReconnectFailures ?? 3;
  const pollIntervalMs = options.pollIntervalMs ?? 2000;
  let lastId = "0";
  let failures = 0;
  let stopped = false;
  let controller: AbortController | null = null;
  let pollTimer: ReturnType<typeof setInterval> | null = null;

  function handleFrame(frame: SseEvent): void {
    if (frame.id) {
      if (seen.has(frame.id)) return;
      seen.add(frame.id);
      lastId = frame.id;
    }
    events.value.push(frame);
    if (frame.event === "run.finished") {
      void finishFromReport();
    }
  }

  async function finishFromReport(): Promise<void> {
    try {
      const report = await getRunReport(runId);
      options.onFinished?.(report);
    } catch {
      // 报告读取失败不影响已收到的终态事件；轮询仍会继续到用户离开页面。
    }
    stop();
  }

  function startPolling(): void {
    if (pollTimer !== null) return;
    connectionState.value = "polling";
    pollTimer = setInterval(async () => {
      try {
        const report = await getRunReport(runId);
        options.onFinished?.(report);
        if (TERMINAL.has(report.status)) stop();
      } catch {
        // 网络恢复后继续轮询；401 由 apiFetch 统一处理。
      }
    }, pollIntervalMs);
  }

  async function connect(): Promise<void> {
    if (stopped) return;
    controller = new AbortController();
    connectionState.value = failures > 0 ? "reconnecting" : "connecting";
    try {
      const token = getAuthToken();
      const response = await fetchImpl(
        `/api/v1/runs/${runId}/events?after=${encodeURIComponent(lastId)}`,
        {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          signal: controller.signal,
        },
      );
      if (response.status === 401) {
        options.onUnauthorized?.();
        stop();
        return;
      }
      if (!response.ok || !response.body) {
        throw new Error(`sse status ${response.status}`);
      }
      connectionState.value = "open";
      failures = 0;
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      const parser = createSseParser(handleFrame);
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        parser.feed(decoder.decode(value, { stream: true }));
      }
      if (!stopped) {
        failures += 1;
        if (failures >= maxFailures) startPolling();
        else await reconnect();
      }
    } catch (error) {
      if (stopped || (error instanceof DOMException && error.name === "AbortError")) return;
      failures += 1;
      if (failures >= maxFailures) {
        startPolling();
      } else {
        await reconnect();
      }
    }
  }

  async function reconnect(): Promise<void> {
    connectionState.value = "reconnecting";
    await new Promise((resolve) => setTimeout(resolve, 300));
    await connect();
  }

  async function start(after = "0"): Promise<void> {
    stopped = false;
    lastId = after;
    seen.clear();
    events.value = [];
    failures = 0;
    await connect();
  }

  function stop(): void {
    stopped = true;
    controller?.abort();
    controller = null;
    if (pollTimer !== null) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
    connectionState.value = "closed";
  }

  onScopeDispose(stop);

  return { events, connectionState, start, stop };
}
