import { expect, test } from "@playwright/test";

import {
  createCase,
  createDemoEnvironment,
  createProject,
  gotoApp,
  loginUi,
  registerAndLogin,
  startRun,
  waitForRun,
} from "./helpers";

test("错误标题导致第 3 步失败、后续跳过", async ({ page, request }) => {
  const suffix = Date.now();
  const username = `e2e_failure_${suffix}`;
  const session = await registerAndLogin(request, username);
  const project = await createProject(request, session, `E2E 失败 ${suffix}`);
  const environment = await createDemoEnvironment(request, session, project.id);
  const testCase = await createCase(
    request,
    session,
    project.id,
    "错误标题用例",
    "definitely-wrong-title",
  );
  const run = await startRun(request, session, project.id, testCase.id, environment.id);
  await waitForRun(request, session, run.run_id, "failed");

  await loginUi(page, username);
  await gotoApp(page, `/runs/${run.run_id}`);
  await expect(page.locator('.status[data-status="failed"]').first()).toBeVisible();
  await expect(page.getByText("断言失败：后续步骤已跳过")).toBeVisible();
  await expect(page.locator('.status[data-status="skipped"]')).toHaveCount(2);
  await expect(page.locator('.status[data-status="skipped"]').first()).toBeVisible();
  if (process.env.E2E_CAPTURE === "1") {
    await page.screenshot({ path: "../docs/screenshots/run-failed.png", fullPage: true });
  }
});
