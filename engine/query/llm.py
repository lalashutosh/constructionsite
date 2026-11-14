"""Optional LLM client (only used when LLM_PROVIDER != none). Reuses the endpoint, auth and ledger logic of
scripts/verda.py (per-model base URL, Bearer key or Modal-Key/Modal-Secret headers, cost ledger, budget cap).
The LLM never produces a number: callers only ask it for a template class or a query_spec."""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import time
from dataclasses import dataclass
from typing import Optional, Protocol

ROOT = pathlib.Path(__file__).resolve().parents[2]


@dataclass
class LLMReply:
    text: str
    tokens_in: int = 0
    tokens_out: int = 0
    usd: float = 0.0


class LLM(Protocol):
    def complete(self, system: str, user: str, max_tokens: int = 400) -> LLMReply: ...


def provider() -> str:
    return os.environ.get("LLM_PROVIDER", "none").strip().lower() or "none"


def _verda_module():
    spec = importlib.util.spec_from_file_location("plumb_verda_script", ROOT / "scripts" / "verda.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


class VerdaLLM:
    """provider verda | featherless; model tier from LLM_MODEL_KIND (fast|strong, default fast)."""

    def __init__(self, prov: str = "verda", kind: Optional[str] = None):
        self.v = _verda_module()
        self.prov = prov
        self.kind = kind or os.environ.get("LLM_MODEL_KIND", "fast")
        self.no_think = False

    def complete_vision(self, system: str, user: str, image_png: bytes, max_tokens: int = 400) -> LLMReply:
        """Same endpoint, OpenAI-style image content. Raises if the model cannot take images."""
        import base64
        url = "data:image/png;base64," + base64.b64encode(image_png).decode()
        return self.complete(system, [{"type": "text", "text": user},
                                      {"type": "image_url", "image_url": {"url": url}}], max_tokens)

    def complete(self, system: str, user, max_tokens: int = 400) -> LLMReply:
        import httpx

        v, env = self.v, self.v.load_env()
        pre = "VERDA" if self.prov == "verda" else "FEATHERLESS"
        k = self.kind.upper()
        key = env.get(f"{pre}_API_KEY", "")
        base = (env.get(f"{pre}_BASE_URL_{k}") or env.get(f"{pre}_BASE_URL", "")).rstrip("/")
        model = env.get(f"{pre}_MODEL_{k}") or env.get(f"{pre}_MODEL", "")
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = key if key.lower().startswith("bearer ") else f"Bearer {key}"
        elif self.prov == "verda" and env.get("MODAL_TOKEN_ID") and env.get("MODAL_TOKEN_SECRET"):
            headers["Modal-Key"], headers["Modal-Secret"] = env["MODAL_TOKEN_ID"], env["MODAL_TOKEN_SECRET"]
        if not (base and model and len(headers) > 1):
            raise RuntimeError(f"{self.prov}: endpoint/model/auth not configured in .env")
        if v.spent() >= float(env.get("BUDGET_VERDA_USD", "0") or 0):
            raise RuntimeError("LLM budget reached")
        body = {"model": model, "max_tokens": max_tokens, "temperature": 0,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if self.no_think:                   # judge-style calls: answer directly, no hidden reasoning tokens
            body["chat_template_kwargs"] = {"thinking": False, "enable_thinking": False}
            body["reasoning_effort"] = "low"
        r = httpx.post(f"{base}/chat/completions", json=body, timeout=60, headers=headers)
        r.raise_for_status()
        data = r.json()
        text = data["choices"][0]["message"].get("content") or ""
        u = data.get("usage") or {}
        tin, tout = int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0))
        pin, pout = v.DEFAULT_PRICES.get(self.kind, (0.15, 0.60))
        pin = float(env.get(f"VERDA_PRICE_{k}_IN", pin))
        pout = float(env.get(f"VERDA_PRICE_{k}_OUT", pout))
        usd = tin / 1e6 * pin + tout / 1e6 * pout
        v.LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with v.LEDGER.open("a") as f:
            f.write(json.dumps({"t": time.time(), "provider": self.prov, "model": model, "kind": self.kind,
                                "tokens_in": tin, "tokens_out": tout, "usd": round(usd, 6),
                                "task": "integrator"}) + "\n")
        return LLMReply(text, tin, tout, usd)


def default_llm() -> Optional[LLM]:
    """None when LLM_PROVIDER=none. `anthropic` is reserved for the live demo and not wired here."""
    p = provider()
    if p in ("verda", "featherless"):
        llm = VerdaLLM(p)
        llm.no_think = True          # planner/classifier want short JSON, not hidden reasoning that eats the budget
        return llm
    return None
