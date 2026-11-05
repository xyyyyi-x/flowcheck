import { startRun } from "../api/runs";
import type { RunCreated } from "../api/types";

export function newIdempotencyKey(): string {
  return crypto.randomUUID();
}

type StartFn = (
  projectId: string,
  caseId: string,
  environmentId: string,
  key: string,
) => Promise<RunCreated>;

export class RunSubmitter {
  key = newIdempotencyKey();
  private pending: Promise<RunCreated> | null = null;

  constructor(private readonly start: StartFn = startRun) {}

  submit(projectId: string, caseId: string, environmentId: string): Promise<RunCreated> {
    if (this.pending) return this.pending;
    this.pending = this.start(projectId, caseId, environmentId, this.key)
      .then((result) => {
        // 已确定创建了 run：下一次主动执行必须使用新的幂等键。
        this.key = newIdempotencyKey();
        return result;
      })
      .finally(() => {
        this.pending = null;
      });
    return this.pending;
  }

  reset(): void {
    this.key = newIdempotencyKey();
    this.pending = null;
  }
}
