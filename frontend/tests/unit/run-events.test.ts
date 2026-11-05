import { describe, expect, it } from "vitest";

import { createSseParser, type SseEvent } from "../../src/api/sse";

describe("SSE parser", () => {
  it("handles UTF-8 Chinese split across chunks", () => {
    const received: SseEvent[] = [];
    const parser = createSseParser((event) => received.push(event));
    parser.feed('id: 7\nevent: step.finished\ndata: {"name":"登');
    parser.feed('录","status":"passed"}\n\n');
    expect(received).toHaveLength(1);
    expect(received[0].id).toBe("7");
    expect(received[0].event).toBe("step.finished");
    expect(received[0].data.name).toBe("登录");
  });

  it("ignores heartbeat comments and parses multiple frames", () => {
    const received: SseEvent[] = [];
    const parser = createSseParser((event) => received.push(event));
    parser.feed(": heartbeat\n\n");
    parser.feed('id: 1\nevent: run.queued\ndata: {"status":"queued"}\n\n');
    parser.feed('id: 2\nevent: run.finished\ndata: {"status":"passed"}\n\n');
    expect(received.map((item) => item.event)).toEqual(["run.queued", "run.finished"]);
    expect(received.map((item) => item.id)).toEqual(["1", "2"]);
  });

  it("skips malformed JSON data without throwing", () => {
    const received: SseEvent[] = [];
    const parser = createSseParser((event) => received.push(event));
    parser.feed("id: 1\nevent: broken\ndata: {oops\n\n");
    expect(received).toHaveLength(0);
  });
});
