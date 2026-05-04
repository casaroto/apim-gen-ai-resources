import { chromium } from "playwright";

const url = "http://localhost:8002/";
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext();
const page = await ctx.newPage();

page.on("console", m => console.log("[browser]", m.type(), m.text()));
page.on("pageerror", e => console.log("[pageerror]", e.message));

await page.goto(url, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);

console.log("URL:", page.url());
console.log("TITLE:", await page.title());

const snippet = await page.content();
console.log("HTML length:", snippet.length);

const navLinks = await page.$$eval("a", as => as.map(a => ({ text: a.textContent.trim().slice(0, 40), href: a.getAttribute("href") })).filter(a => a.text && a.text.length < 40));
console.log("Links (first 40):", navLinks.slice(0, 40));

await page.screenshot({ path: "/tmp/kong-manager.png", fullPage: true });
console.log("screenshot: /tmp/kong-manager.png");

await browser.close();
