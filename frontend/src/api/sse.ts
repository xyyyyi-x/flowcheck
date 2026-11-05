import { createParser } from "eventsource-parser";

export interface SseEvent {
  id: string;
  event: string;
  data: Record<string, unknown>;
}

export function createSseParser(onEvent: (event: SseEvent) => void) {
  return createParser({
    onEvent: (message) => {
      let data: Record<string, unknown> = {};
      if (message.data) {
        try {
          data = JSON.parse(message.data) as Record<string, unknown>;
        } catch {
          return;
        }
      }
      onEvent({ id: message.id ?? "", event: message.event ?? "message", data });
    },
  });
}
