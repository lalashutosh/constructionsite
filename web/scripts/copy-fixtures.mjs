// Copies contracts/fixtures/*.json into public/fixtures/ (no-op if source is missing).
import { cpSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const src = join(here, "..", "..", "contracts", "fixtures");
const dst = join(here, "..", "public", "fixtures");
if (existsSync(src)) {
  mkdirSync(dst, { recursive: true });
  cpSync(src, dst, { recursive: true });
  console.log("fixtures copied");
}

// claims.json: measured numbers from evalkit (scalars and short arrays only; no run paths).
import { readFileSync, writeFileSync } from "node:fs";
const claimsSrc = join(here, "..", "..", "evalkit", "out", "latest", "claims.json");
if (existsSync(claimsSrc)) {
  const all = JSON.parse(readFileSync(claimsSrc, "utf8"));
  const keep = {};
  for (const [k, v] of Object.entries(all)) {
    if (k === "run" || k === "commit" || k === "reliability_cv") continue;
    keep[k] = v;
  }
  // merge the cross-run summary (with/without siblings, per source, router, LLM ledger) from scripts/make_claims.py
  const summary = join(here, "..", "..", "evalkit", "out", "summary_claims.json");
  if (existsSync(summary)) Object.assign(keep, JSON.parse(readFileSync(summary, "utf8")));
  writeFileSync(join(here, "..", "public", "claims.json"), JSON.stringify(keep, null, 1));
  console.log("claims copied");
}
