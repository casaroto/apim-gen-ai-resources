// Drives Kong Manager OSS (port 8002) end-to-end:
//   - creates a Gateway Service "books-service" -> http://backend:3000
//   - creates a Route "books-route" with path /books-api
// Verifies via Admin API after each step.

import { chromium } from "playwright";

const MANAGER = "http://localhost:8002";
const ADMIN = "http://localhost:8001";
const SERVICE_NAME = "books-service";
const SERVICE_URL = "http://backend:3000";
const ROUTE_NAME = "books-route";
const ROUTE_PATH = "/books-api";

async function adminDelete(path) {
  const res = await fetch(ADMIN + path, { method: "DELETE" });
  if (![204, 404].includes(res.status)) throw new Error(`DELETE ${path} -> ${res.status}`);
}

async function adminGet(path) {
  const res = await fetch(ADMIN + path);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`GET ${path} -> ${res.status}`);
  return res.json();
}

async function clean() {
  console.log("→ cleaning any existing service/route");
  await adminDelete(`/routes/${ROUTE_NAME}`);
  await adminDelete(`/services/${SERVICE_NAME}`);
}

async function pollFor(fn, label, timeoutMs = 10000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const v = await fn();
    if (v) return v;
    await new Promise(r => setTimeout(r, 300));
  }
  throw new Error(`timed out waiting for ${label}`);
}

async function clickSave(page) {
  // The form has multiple type=submit buttons (incl. "View Advanced Fields").
  // Target the bottom Save button by exact text.
  await page.getByRole("button", { name: /^Save$/ }).click();
}

async function createServiceUI(page) {
  console.log("→ creating service via Manager UI");
  await page.goto(`${MANAGER}/services/create`, { waitUntil: "networkidle" });
  await page.fill('input[name="name"]', SERVICE_NAME);
  await page.fill('input[name="url"]', SERVICE_URL);
  await clickSave(page);

  const svc = await pollFor(
    () => adminGet(`/services/${SERVICE_NAME}`),
    "service to appear in Admin API"
  );
  console.log(`   service created: ${svc.name} -> ${svc.protocol}://${svc.host}:${svc.port}${svc.path ?? ""}`);
}

async function createRouteUI(page) {
  console.log("→ creating route via Manager UI");
  await page.goto(`${MANAGER}/routes/create`, { waitUntil: "networkidle" });
  await page.waitForTimeout(500);

  // Name
  await page.getByPlaceholder("Enter a unique name").fill(ROUTE_NAME);

  // Service select — kongponent uses an input with data-testid; click to open list, then click option.
  const serviceInput = page.locator('[data-testid="route-form-service-id"]');
  await serviceInput.click();
  await page.waitForTimeout(400);
  await serviceInput.fill(SERVICE_NAME);
  await page.waitForTimeout(400);
  await page.locator('.select-item-container, [role="option"]').filter({ hasText: SERVICE_NAME }).first().click({ timeout: 5000 });

  // Paths
  await page.getByPlaceholder("Enter a path").fill(ROUTE_PATH);

  await clickSave(page);

  const route = await pollFor(
    () => adminGet(`/routes/${ROUTE_NAME}`),
    "route to appear in Admin API"
  );
  console.log(`   route created: ${route.name} paths=${JSON.stringify(route.paths)} strip_path=${route.strip_path}`);
}

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext();
const page = await ctx.newPage();
page.on("pageerror", e => console.log("[pageerror]", e.message));

try {
  await clean();
  await createServiceUI(page);
  await createRouteUI(page);
  console.log("✅ done — verify with: curl http://localhost:8000" + ROUTE_PATH + "/health");
} catch (e) {
  console.error("❌ failed:", e.message);
  await page.screenshot({ path: "/tmp/kong-failure.png", fullPage: true });
  console.error("   screenshot: /tmp/kong-failure.png");
  process.exitCode = 1;
} finally {
  await browser.close();
}
