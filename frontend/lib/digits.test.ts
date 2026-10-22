import assert from "node:assert/strict";
import { test } from "node:test";
import { parseCount, toLatin } from "./digits.ts";

test("Persian and Arabic-Indic digits become ASCII", () => {
  assert.equal(toLatin("۰۹۱۲۳۴۵۶۷۸۹"), "09123456789");
  assert.equal(toLatin("٠٩١٢٣٤٥٦٧٨٩"), "09123456789");
  assert.equal(toLatin("0912-۳۴۵"), "0912-345");
});

test("step counts survive Persian keyboards, separators and pastes", () => {
  assert.equal(parseCount("۸۰۰۰", 40000), 8000);
  assert.equal(parseCount("۸٬۰۰۰", 40000), 8000); // Persian thousands separator
  assert.equal(parseCount("8,000", 40000), 8000);
  assert.equal(parseCount("abc", 40000), 0);
  assert.equal(parseCount("", 40000), 0);
});

test("the cap holds, including absurd input", () => {
  assert.equal(parseCount("99999", 40000), 40000);
  assert.equal(parseCount("9".repeat(40), 40000), 40000);
});
