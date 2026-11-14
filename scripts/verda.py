"""One-shot calls to an OpenAI-compatible inference API (Verda by default, Featherless as backup).

    .venv/bin/python scripts/verda.py --ping
    .venv/bin/python scripts/verda.py --model fast --prompt-file cache/verda/task.md --context a.py b.md --out cache/verda/out.md
    .venv/bin/python scripts/verda.py --spent

Keys come from .env (never printed). The VERDA_* names are generic: any OpenAI-compatible endpoint works
(Verda, Modal Auto Endpoints, ...). Featherless uses FEATHERLESS_* with --provider featherless.
  VERDA_BASE_URL            OpenAI-compatible base, usually ending in /v1
  VERDA_BASE_URL_FAST/_STRONG  optional per-model base URL (Modal gives one URL per endpoint)
  VERDA_MODEL_FAST/_STRONG  model ids
  Auth, first match wins:   VERDA_API_KEY -> "Authorization: Bearer <key>"
                            MODAL_TOKEN_ID + MODAL_TOKEN_SECRET -> "Modal-Key" / "Modal-Secret" headers
Prices (USD per 1M tokens) from VERDA_PRICE_{FAST,STRONG}_{IN,OUT}; defaults below. Every call is appended to
logs/verda_cost.jsonl; a call is refused when the running total would pass BUDGET_VERDA_USD.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "logs" / "verda_cost.jsonl"
DEFAULT_PRICES = {"fast": (0.15, 0.60), "strong": (2.00, 10.00)}
MAX_FILE_CHARS, MAX_TOTAL_CHARS = 60_000, 300_000


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def spent() -> float:
    if not LEDGER.exists():
        return 0.0
    return sum(json.loads(l).get("usd", 0.0) for l in LEDGER.read_text().splitlines() if l.strip())


def build_context(files: list[str]) -> str:
    parts, total = [], 0
    for f in files:
        p = (ROOT / f).resolve()
        if p.name.startswith(".env") or ROOT not in p.parents and p != ROOT:
            sys.exit(f"refused context file: {f}")
        text = p.read_text(errors="replace")[:MAX_FILE_CHARS]
        total += len(text)
        if total > MAX_TOTAL_CHARS:
            parts.append("\n[context truncated: total size limit]")
            break
        parts.append(f"\n===== FILE: {f} =====\n{text}")
    return "".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=["verda", "featherless"], default="verda")
    ap.add_argument("--model", choices=["fast", "strong"], default="fast")
    ap.add_argument("--prompt-file")
    ap.add_argument("--prompt")
    ap.add_argument("--context", nargs="*", default=[])
    ap.add_argument("--system", default="You are a precise senior engineer. Answer with the requested artifact only.")
    ap.add_argument("--out")
    ap.add_argument("--max-tokens", type=int, default=4000)
    ap.add_argument("--ping", action="store_true")
    ap.add_argument("--no-think", action="store_true", help="answer directly: no hidden reasoning tokens")
    ap.add_argument("--spent", action="store_true")
    a = ap.parse_args()

    if a.spent:
        print(f"verda spent: ${spent():.4f}")
        return 0

    env = load_env()
    pre = "VERDA" if a.provider == "verda" else "FEATHERLESS"
    key = env.get(f"{pre}_API_KEY", "")
    base = (env.get(f"{pre}_BASE_URL_{a.model.upper()}") or env.get(f"{pre}_BASE_URL", "")).rstrip("/")
    model = env.get(f"{pre}_MODEL_{a.model.upper()}") or env.get(f"{pre}_MODEL", "")
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = key if key.lower().startswith("bearer ") else f"Bearer {key}"
    elif a.provider == "verda" and env.get("MODAL_TOKEN_ID") and env.get("MODAL_TOKEN_SECRET"):
        headers["Modal-Key"], headers["Modal-Secret"] = env["MODAL_TOKEN_ID"], env["MODAL_TOKEN_SECRET"]
    if not (base and model and len(headers) > 1):
        missing = [n for n, ok in ((f"{pre}_BASE_URL(_{a.model.upper()})", base),
                                   (f"{pre}_MODEL(_{a.model.upper()})", model),
                                   (f"{pre}_API_KEY or MODAL_TOKEN_ID+MODAL_TOKEN_SECRET", len(headers) > 1)) if not ok]
        print(f"{a.provider} [{a.model}]: missing or empty in {ROOT / '.env'}: {', '.join(missing)}")
        if any(k.startswith("export ") for k in env):
            print("  note: drop 'export ' prefixes; this parser does not strip them")
        return 3
    budget = float(env.get("BUDGET_VERDA_USD", "0") or 0)
    if spent() >= budget:
        print(f"refused: budget ${budget:.2f} reached (spent ${spent():.4f})")
        return 4

    if a.ping:
        user = "Reply with the single word: ok"
        a.max_tokens = 5
    else:
        if not (a.prompt or a.prompt_file):
            sys.exit("need --prompt or --prompt-file")
        user = a.prompt or (ROOT / a.prompt_file).read_text()
        user += build_context(a.context)

    import httpx

    body = {"model": model, "max_tokens": a.max_tokens, "temperature": 0.2,
            "messages": [{"role": "system", "content": a.system}, {"role": "user", "content": user}]}
    if a.no_think:                       # thinking models otherwise spend max_tokens on hidden reasoning
        body["chat_template_kwargs"] = {"thinking": False, "enable_thinking": False}
        body["reasoning_effort"] = "low"
    data, err = None, ""
    for attempt in range(4):
        print(f"[{a.provider}:{a.model}] attempt {attempt + 1}/4 -> {base} (cold start can take minutes)"
              + (f", last error {err}" if err else ""), file=sys.stderr, flush=True)
        try:
            r = httpx.post(f"{base}/chat/completions", json=body, timeout=300, headers=headers)
            if r.status_code in (401, 403):
                print(f"{a.provider}: HTTP {r.status_code} (auth). Check the key or token headers and the base URL.")
                return 6
            if r.status_code in (429, 500, 502, 503, 504):
                err = f"HTTP {r.status_code}"
                time.sleep(5 * 2 ** attempt)
                continue
            if r.status_code >= 400:
                print(f"{a.provider}: HTTP {r.status_code} from {base}/chat/completions: {r.text[:300]}")
                if r.status_code == 404 and not base.endswith("/v1"):
                    print("  hint: base URL probably needs a trailing /v1")
                return 7
            data = r.json()
            break
        except httpx.HTTPError as e:
            err = type(e).__name__
            time.sleep(5 * 2 ** attempt)
    if data is None:
        print(f"{a.provider} call failed: {err}")
        return 5

    text = data["choices"][0]["message"].get("content") or ""
    u = data.get("usage") or {}
    tin, tout = int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0))
    pin = float(env.get(f"VERDA_PRICE_{a.model.upper()}_IN", DEFAULT_PRICES[a.model][0]))
    pout = float(env.get(f"VERDA_PRICE_{a.model.upper()}_OUT", DEFAULT_PRICES[a.model][1]))
    usd = tin / 1e6 * pin + tout / 1e6 * pout
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a") as f:
        f.write(json.dumps({"t": time.time(), "provider": a.provider, "model": model, "kind": a.model,
                            "tokens_in": tin, "tokens_out": tout, "usd": round(usd, 6),
                            "task": a.prompt_file or ("ping" if a.ping else "inline")}) + "\n")
    if a.out:
        out = ROOT / a.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text)
    else:
        print(text)
    print(f"[{a.provider}:{a.model}] tokens {tin}+{tout} usd {usd:.4f} total ${spent():.4f}"
          + (f" -> {a.out}" if a.out else ""), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())