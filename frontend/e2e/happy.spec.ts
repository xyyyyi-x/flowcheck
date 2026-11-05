import { expect, test } from "@playwright/test";

import {
  createCase,
  createDemoEnvironment,
  createProject,
  gotoApp,
  loginUi,
  registerAndLogin,
} from "./helpers";

test("五步文章回归在浏览器中全通过", async ({ page, request }) => {
  const suffix = Date.now();
  const username = `e2e_happy_${suffix}`;
  const session = await registerAndLogin(request, username);
  const project = await createProject(request, session, `E2E 成功 ${suffix}`);
  const environment = await createDemoEnvironment(request, session, project.id);
  await createCase(request, session, project.id, "五步成功");

  await loginUi(page, username);
  await gotoApp(page, `/projects/${project.id}/runs`);
  await page.getByRole("button", { name: "执行用例" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.locator(".el-select").nth(0).click();
  await page.getByRole("option", { name: "五步成功" }).click();
  await dialog.locator(".el-select").nth(1).click();
  await page.getByRole("option", { name: /Compose Demo/ }).click();
  await page.getByRole("button", { name: "开始执行" }).click();

  await expect(page).toHaveURL(/\/runs\/[0-9a-f-]+$/);
  await expect(page.locator('.status[data-status="passed"]').first()).toBeVisible({
    timeout: 60_000,
  });
  await expect(page.getByText("总步骤 5")).toBeVisible();
  await expect(page.locator('.status[data-status="passed"]')).toHaveCount(6, {
    timeout: 10_000,
  });
  await expect(page.getByText("实时更新中").or(page.getByText("已停止"))).toBeVisible();
  if (process.env.E2E_CAPTURE === "1") {
    await page.screenshot({ path: "../docs/screenshots/run-passed.png", fullPage: true });
  }
});
