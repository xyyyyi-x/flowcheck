import { defineConfig, devices } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../..",
);

function loadEnvFile(name: string): Record<string, string> {
  const file = path.join(projectRoot, name);
  if (!fs.existsSync(file)) return {};
  const values: Record<string, string> = {};
  for (const line of fs.readFileSync(file, "utf-8").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) continue;
    const index = trimmed.indexOf("=");
    values[trimmed.slice(0, index)] = trimmed.slice(index + 1);
  }
  return values;
}

const env = { ...loadEnvFile(".env"), ...loadEnvFile(".env.e2e") };
process.env.API_PORT ??= env.API_PORT ?? "8000";
process.env.WEB_PORT ??= env.WEB_PORT ?? "8080";
process.env.DEMO_USERNAME ??= env.DEMO_USERNAME ?? "demo";
process.env.DEMO_PASSWORD ??= env.DEMO_PASSWORD;

export default defineConfig({
  testDir: ".",
  testMatch: ["*.spec.ts"],
  fullyParallel: false,
  workers: 1,
  timeout: 90_000,
  expect: { timeout: 20_000 },
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? `http://127.0.0.1:${env.WEB_PORT ?? "8080"}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    headless: true,
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        ...(process.env.E2E_BROWSER_CHANNEL
          ? { channel: process.env.E2E_BROWSER_CHANNEL as "chrome" | "msedge" }
          : {}),
      },
    },
  ],
});
