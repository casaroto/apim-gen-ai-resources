import { chromium } from "playwright";

const browser = await chromium.launch({ headless: true });
const page = await browser.newContext().then(c => c.newPage());

await page.goto("http://localhost:8002/services/create", { waitUntil: "networkidle" });
await page.waitForTimeout(1500);

console.log("URL:", page.url());
console.log("TITLE:", await page.title());

const inputs = await page.$$eval("input,textarea,select", els =>
  els.map(e => ({ tag: e.tagName, type: e.type, name: e.name, id: e.id, placeholder: e.placeholder, label: e.getAttribute("aria-label") || "" }))
);
console.log("FORM CONTROLS:", JSON.stringify(inputs, null, 2));

const buttons = await page.$$eval("button", bs => bs.map(b => ({ text: b.textContent.trim().slice(0, 30), type: b.type, ariaLabel: b.getAttribute("aria-label") || "" })));
console.log("BUTTONS:", JSON.stringify(buttons, null, 2));

await page.screenshot({ path: "/tmp/kong-service-form.png", fullPage: true });
await browser.close();
