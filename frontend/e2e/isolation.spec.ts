import { expect, test } from "@playwright/test";

import {
  createProject,
  fillLogin,
  gotoApp,
  loginUi,
  registerAndLogin,
} from "./helpers";

test("用户 B 无法查看用户 A 的项目", async ({ page, request }) => {
  const suffix = Date.now();
  const ownerA = await registerAndLogin(request, `e2e_owner_a_${suffix}`);
  const projectA = await createProject(request, ownerA, `A 私有项目 ${suffix}`);
  const ownerB = `e2e_owner_b_${suffix}`;
  await registerAndLogin(request, ownerB);

  await loginUi(page, ownerB);
  await gotoApp(page, "/projects");
  await expect(page.getByText(`A 私有项目 ${suffix}`)).toHaveCount(0);

  // 整页刷新会按设计丢失内存 Token；重新登录后应回到原路径并得到 404。
  await page.goto(`/projects/${projectA.id}/overview`);
  await expect(page).toHaveURL(/\/auth\/login\?redirect=/);
  await fillLogin(page, ownerB);
  await expect(page).toHaveURL(new RegExp(`/projects/${projectA.id}/overview`));
  await expect(page.getByText("资源不存在或无权访问")).toBeVisible();
});
