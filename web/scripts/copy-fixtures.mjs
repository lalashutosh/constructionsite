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
