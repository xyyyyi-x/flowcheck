import { describe, expect, it, vi } from "vitest";

import type { RunCreated } from "../../src/api/types";
import { RunSubmitter } from "../../src/utils/runSubmission";

const success: RunCreated = { run_id: "r1", status: "queued", reused: false };

describe("RunSubmitter", () => {
  it("reuses the same key for a retry after a failed transfer", async () => {
    const start = vi
      .fn()
      .mockRejectedValueOnce(new Error("network"))
      .mockResolvedValueOnce(success);
    const submitter = new RunSubmitter(start);
    const firstKey = submitter.key;
    await expect(submitter.submit("p", "c", "e")).rejects.toThrow("network");
    expect(submitter.key).toBe(firstKey);
    await submitter.submit("p", "c", "e");
    expect(start.mock.calls[0][3]).toBe(firstKey);
    expect(start.mock.calls[1][3]).toBe(firstKey);
  });

  it("uses a new key after a definite run was created", async () => {
    const start = vi.fn().mockResolvedValue(success);
    const submitter = new RunSubmitter(start);
    const firstKey = submitter.key;
    await submitter.submit("p", "c", "e");
    expect(submitter.key).not.toBe(firstKey);
    await submitter.submit("p", "c", "e");
    expect(start.mock.calls[1][3]).not.toBe(firstKey);
  });

  it("submits only once when clicked twice while in flight", async () => {
    let resolveStart: (value: RunCreated) => void = () => undefined;
    const start = vi.fn(
      () => new Promise<RunCreated>((resolve) => (resolveStart = resolve)),
    );
    const submitter = new RunSubmitter(start);
    const first = submitter.submit("p", "c", "e");
    const second = submitter.submit("p", "c", "e");
    expect(second).toBe(first);
    resolveStart(success);
    await expect(first).resolves.toEqual(success);
    expect(start).toHaveBeenCalledTimes(1);
  });
});
