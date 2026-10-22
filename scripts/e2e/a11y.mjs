import puppeteer from "puppeteer-core";
import { readFileSync } from "node:fs";
const axe = readFileSync(new URL("./node_modules/axe-core/axe.min.js", import.meta.url), "utf8");
const BASE = process.env.BASE_URL ?? "http://127.0.0.1:3330";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const browser = await puppeteer.launch({ executablePath: process.env.CHROME ?? "/usr/bin/google-chrome", headless: "new", args: ["--no-sandbox", "--disable-gpu"] });
const out = {};
let phoneN = 0;
for (const [lang, theme] of [["fa", "light"], ["fa", "dark"], ["en", "light"], ["en", "dark"]]) {
  const ctx = await browser.createBrowserContext(); const page = await ctx.newPage();
  await page.setViewport({ width: 1280, height: 900 });
  await page.setCookie({ name: "lang", value: lang, url: BASE });
  await page.evaluateOnNewDocument((th) => { try { localStorage.theme = th; } catch {} }, theme);
  const run = async (name) => {
    await page.evaluate(axe);
    const r = await page.evaluate(async () => (await axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa", "best-practice"] } })).violations.map((v) => ({ id: v.id, impact: v.impact, n: v.nodes.length, help: v.help, sample: v.nodes[0].target.join(" "), summary: (v.nodes[0].failureSummary || "").split("\n").slice(1, 3).join(" ").slice(0, 160) })));
    out[`${name} ${lang}/${theme}`] = r;
  };
  await page.goto(BASE + "/", { waitUntil: "networkidle2", timeout: 90000 }); await sleep(1500);
  await run("login");
  const phone = `091200000${["02", "03", "04", "05"][phoneN++]}`;
  await page.type('input[name="phone"]', phone); await page.click('button[type="submit"]'); await page.waitForSelector('input[name="code"]');
  await sleep(400); await page.evaluate(() => [...document.querySelectorAll("button")].find((b) => b.querySelector("b.tabular-nums"))?.click());
  await page.waitForFunction(() => !document.querySelector('input[name="code"]'), { timeout: 30000 }); await sleep(2500);
  for (const path of ["/", "/pacts", "/wallet", "/community", "/account", "/business"]) { await page.goto(BASE + path, { waitUntil: "networkidle2", timeout: 90000 }); await sleep(2200); await run(path); }
  await ctx.close();
}
await browser.close();
const agg = {};
for (const [k, v] of Object.entries(out)) for (const x of v) { const key = `${x.impact}|${x.id}|${x.help}`; (agg[key] ??= { n: 0, where: new Set(), sample: x.sample, summary: x.summary }); agg[key].n += x.n; agg[key].where.add(k.split(" ")[0]); }
console.log(JSON.stringify(Object.entries(agg).map(([k, v]) => ({ k, nodes: v.n, pages: [...v.where].join(","), sample: v.sample, why: v.summary })), null, 1));
