import puppeteer from "puppeteer-core";
const OUT = process.env.OUT ?? "./out";
const BASE = process.env.BASE_URL ?? "http://127.0.0.1:3330";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const browser = await puppeteer.launch({ executablePath: process.env.CHROME ?? "/usr/bin/google-chrome", headless: "new", args: ["--no-sandbox", "--disable-gpu", "--font-render-hinting=none"] });
const problems = [];
async function newPage(w, h, { lang = "fa", theme = "light", mobile = false } = {}) {
  const ctx = await browser.createBrowserContext();
  const page = await ctx.newPage();
  page.on("close", () => ctx.close().catch(() => {}));
  await page.setViewport({ width: w, height: h, deviceScaleFactor: mobile ? 2 : 1, isMobile: mobile, hasTouch: mobile });
  await page.setCookie({ name: "lang", value: lang, url: BASE });
  await page.evaluateOnNewDocument((th) => { try { localStorage.theme = th; } catch {} }, theme);
  page.on("console", (m) => { if (["error", "warning"].includes(m.type())) problems.push(`[console.${m.type()}] ${m.text().slice(0, 200)}`); });
  page.on("pageerror", (e) => problems.push(`[pageerror] ${String(e).slice(0, 200)}`));
  page.on("requestfailed", (r) => problems.push(`[requestfailed] ${r.url().slice(0, 100)} ${r.failure()?.errorText}`));
  return page;
}
async function login(page, phone = "09120000001") {  // 3 codes per phone per 10 min is the server limit, so rotate phones
  await page.goto(BASE + "/", { waitUntil: "networkidle2", timeout: 90000 });
  await page.waitForSelector('input[name="phone"]', { timeout: 30000 });
  await page.type('input[name="phone"]', phone);
  await page.click('button[type="submit"]');
  await page.waitForSelector('input[name="code"]', { timeout: 30000 });
  await sleep(400);
  await page.evaluate(() => [...document.querySelectorAll("button")].find((b) => b.querySelector("b.tabular-nums"))?.click());
  await page.waitForFunction(() => !document.querySelector('input[name="code"]'), { timeout: 30000 });
  await sleep(1800);
}
const shot = async (page, name) => { await page.screenshot({ path: `${OUT}/${name}.png`, type: "png" }); };
const result = {};

// 1. Login screen, signed out
{
  const page = await newPage(390, 844, { mobile: true });
  await page.goto(BASE + "/", { waitUntil: "networkidle2", timeout: 90000 });
  await page.waitForSelector('input[name="phone"]');
  await sleep(1200);
  result.loginIsGate = !!(await page.$('input[name="phone"]'));
  await shot(page, "login-fa-light-mobile");
  await page.close();
}
{
  const page = await newPage(1440, 900, { lang: "en", theme: "dark" });
  await page.goto(BASE + "/", { waitUntil: "networkidle2", timeout: 90000 });
  await page.waitForSelector('input[name="phone"]');
  await sleep(1200);
  await shot(page, "login-en-dark-desktop");
  await page.close();
}

// 2. Signed in: every page, desktop + mobile, fa light and en dark
for (const cfg of [
  { tag: "fa-light-desktop", w: 1440, h: 900, lang: "fa", theme: "light", mobile: false },
  { tag: "en-dark-desktop", w: 1440, h: 900, lang: "en", theme: "dark", mobile: false },
  { tag: "fa-dark-mobile", w: 390, h: 844, lang: "fa", theme: "dark", mobile: true },
  { tag: "en-light-mobile", w: 390, h: 844, lang: "en", theme: "light", mobile: true, phone: "09120000004" },
]) {
  const page = await newPage(cfg.w, cfg.h, cfg);
  await login(page, cfg.phone);
  for (const [path, name] of [["/", "today"], ["/pacts", "pacts"], ["/wallet", "wallet"], ["/community", "community"], ["/account", "account"], ["/business", "business"]]) {
    await page.goto(BASE + path, { waitUntil: "networkidle2", timeout: 90000 });
    await sleep(1600);
    await shot(page, `${name}-${cfg.tag}`);
  }
  // horizontal overflow check (responsiveness)
  result[`overflowX_${cfg.tag}`] = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
  await page.close();
}

// 3. Interaction checks on mobile: sheet opens, drag-to-dismiss works, hold button is keyboard-activatable
{
  const page = await newPage(390, 844, { mobile: true });
  await login(page, "09120000005");
  await page.goto(BASE + "/", { waitUntil: "networkidle2", timeout: 90000 });
  await sleep(1500);
  await page.evaluate(() => document.querySelector("article button.btn-ghost")?.click());
  await page.waitForSelector("dialog[open]", { timeout: 10000 });
  await sleep(800);
  await shot(page, "sheet-open-fa-light-mobile");
  const grab = await page.$(".sheet-grab"); const bb = await grab.boundingBox();
  await page.mouse.move(bb.x + bb.width / 2, bb.y + bb.height / 2); await page.mouse.down();
  for (let i = 1; i <= 12; i++) { await page.mouse.move(bb.x + bb.width / 2, bb.y + bb.height / 2 + i * 30); await sleep(12); }
  await page.mouse.up(); await sleep(1500);
  result.sheetDraggedAway = !(await page.$("dialog[open]"));
  // rubber-band + spring back: small drag, release -> stays open
  await page.evaluate(() => document.querySelector("article button.btn-ghost")?.click());
  await page.waitForSelector("dialog[open]"); await sleep(700);
  const g2 = await (await page.$(".sheet-grab")).boundingBox();
  await page.mouse.move(g2.x + 100, g2.y + 20); await page.mouse.down(); await page.mouse.move(g2.x + 100, g2.y + 60, { steps: 6 }); await sleep(250); await page.mouse.up(); await sleep(1200);
  result.sheetSpringsBack = !!(await page.$("dialog[open]"));
  await page.keyboard.press("Escape"); await sleep(1200);
  result.escClosesSheet = !(await page.$("dialog[open]"));
  await page.close();
}

// 4. Performance snapshot on the dashboard (desktop, fa) with CPU/network as-is
{
  const page = await newPage(1440, 900, { lang: "fa", theme: "dark" });
  await login(page, "09120000006");
  const reqs = []; page.on("response", (r) => { reqs.push([r.url(), Number(r.headers()["content-length"] || 0), r.request().resourceType()]); });
  await page.goto(BASE + "/", { waitUntil: "networkidle0", timeout: 90000 });
  await sleep(1500);
  const m = await page.evaluate(() => {
    const nav = performance.getEntriesByType("navigation")[0];
    const paint = Object.fromEntries(performance.getEntriesByType("paint").map((p) => [p.name, Math.round(p.startTime)]));
    return { domContentLoaded: Math.round(nav.domContentLoadedEventEnd), load: Math.round(nav.loadEventEnd), ...paint };
  });
  const byType = {}; for (const [, len, type] of reqs) byType[type] = (byType[type] || 0) + len;
  result.perf = { ...m, requests: reqs.length, bytesByType: byType, fonts: reqs.filter((r) => r[2] === "font").map((r) => r[0].split("/").pop()) };
  const cdp = await page.createCDPSession(); await cdp.send("Performance.enable");
  const a = (await cdp.send("Performance.getMetrics")).metrics; await sleep(5000); const b = (await cdp.send("Performance.getMetrics")).metrics;
  const g = (ms, n) => ms.find((x) => x.name === n).value;
  result.idle5s = { scriptMs: Math.round((g(b, "ScriptDuration") - g(a, "ScriptDuration")) * 1000), layoutMs: Math.round((g(b, "LayoutDuration") - g(a, "LayoutDuration")) * 1000), taskMs: Math.round((g(b, "TaskDuration") - g(a, "TaskDuration")) * 1000), recalcStyleCount: g(b, "RecalcStyleCount") - g(a, "RecalcStyleCount") };
  await page.close();
}
await browser.close();
console.log(JSON.stringify({ result, problems: [...new Set(problems)].slice(0, 30) }, null, 1));
