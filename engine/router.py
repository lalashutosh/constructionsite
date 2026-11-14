"""Question router: `route(question, path) -> Route(intent, params, kind, lang, layer)`.

Layers, cheapest first, stop at the first confident hit:
  1. evalkit.intents.classify (regex + localized template table)            layer "regex"
  2. language-agnostic nearest template: char n-gram TF-IDF over evalkit/out/intent_labels.jsonl   layer "ngram"
  3. optional LLM template classifier (LLM_PROVIDER != none), once per DISTINCT normalised template, cached
     in cache/templates.json and logged in Cost                              layer "llm"
  4. else intent="unknown" (the pipeline may then try the planner)           layer "none"
The data tables live in evalkit/*.yaml and evalkit/out/intent_labels.jsonl, not in this file."""
from __future__ import annotations

import json
import os
import pathlib
import re
import threading
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

from contracts.proof import Cost

ROOT = pathlib.Path(__file__).resolve().parents[1]
LABELS = ROOT / "evalkit" / "out" / "intent_labels.jsonl"
TEMPLATES_CACHE = pathlib.Path(os.environ.get("PLUMB_CACHE_DIR", str(ROOT / "cache"))) / "templates.json"
NGRAM_THRESHOLD = 0.55


@dataclass
class Route:
    intent: str = "unknown"
    params: dict = field(default_factory=dict)
    kind: str = "count"
    lang: str = "xx"
    layer: str = "none"
    cost: Cost = field(default_factory=Cost)


_KINDS: Optional[dict] = None


def kind_of(intent: str) -> str:
    global _KINDS
    if _KINDS is None:
        from evalkit import intents as I
        _KINDS = {}
        for r in I._rules():
            _KINDS.setdefault(r.name, r.kind)
    return _KINDS.get(intent, "count")


def known_intents() -> list[str]:
    kind_of("x")
    return sorted(_KINDS or {})


def normalise(q: str) -> str:
    """NFKC, casefold, digits and quoted text stripped (the template key)."""
    q = unicodedata.normalize("NFKC", q).casefold()
    q = re.sub(r"['‘’“”«»„‚\"][^'‘’“”«»„‚\"]*['‘’“”«»„‚\"]", " #q# ", q)
    q = re.sub(r"\d+([.,]\d+)?", "#", q)
    return re.sub(r"\s+", " ", q).strip()


def quoted(q: str) -> list[str]:
    return [m[0] or m[1] for m in re.findall(r"'([^']+)'|‘([^’]+)’", q)] + re.findall(r"\"([^\"]+)\"", q)


# ----------------------------------------------------------------------------- layer 2: n-gram NN
class NGramIndex:
    def __init__(self, rows: list[tuple[str, str, str]]):
        """rows = [(normalised template, intent, source)], deduplicated."""
        from sklearn.feature_extraction.text import TfidfVectorizer
        self.templates = [r[0] for r in rows]
        self.intents = [r[1] for r in rows]
        self.sources = [r[2] for r in rows]
        self.vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), sublinear_tf=True)
        self.mat = self.vec.fit_transform(self.templates)

    def nearest(self, norm_q: str, source: Optional[str] = None) -> tuple[str, float]:
        """Nearest template; restricted to the same data source (path folder) when it is known."""
        import numpy as np
        sims = (self.mat @ self.vec.transform([norm_q]).T).toarray().ravel()
        if source and source in self.sources:
            sims = np.where(np.array(self.sources) == source, sims, -1.0)
        i = int(sims.argmax())
        return self.intents[i], float(sims[i])


def _src(path: str) -> str:
    parts = (path or "").split("/")
    return parts[1] if len(parts) > 1 else ""


def _label_rows(exclude_lang: Optional[str] = None) -> list[tuple[str, str, str, str]]:
    seen, out = set(), []
    if not LABELS.exists():
        return out
    for line in LABELS.read_text(encoding="utf-8").splitlines():
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("intent") in (None, "unknown") or d.get("lang") == exclude_lang:
            continue
        key = (normalise(d["question"]), d["intent"], _src(d.get("path", "")))
        if key not in seen:
            seen.add(key)
            out.append((key[0], key[1], key[2], d.get("lang", "xx")))
    return out


_INDEX: Optional[NGramIndex] = None
_INDEX_LOCK = threading.Lock()


def _index() -> Optional[NGramIndex]:
    global _INDEX
    with _INDEX_LOCK:
        if _INDEX is None:
            rows = [(t, i, s) for t, i, s, _ in _label_rows()]
            _INDEX = NGramIndex(rows) if rows else None
    return _INDEX


def _params_from_quotes(intent: str, q: str) -> dict:
    qs = quoted(q)
    if intent in ("room_labelled", "room_area_labelled") and qs:
        return {"label": qs[0]}
    if intent in ("room_area",) and qs:
        m = re.search(r"([\w.\-]*\d[\w.\-]*)", q)
        return {"label": qs[0], "room": m.group(1) if m else None}
    if intent in ("room_net_area", "total_net_area_storey", "walls_side_area_storey", "walls_length_storey",
                  "walls_volume_storey", "slabs_volume_storey", "doors_on_storey", "count_on_storey") and qs:
        p = {"storey": qs[-1]}
        if intent == "room_net_area":
            p["room"] = qs[0]
        return p
    return {}


def lolo_accuracy() -> dict:
    """Leave-one-language-out accuracy of layer 2 over distinct templates: for each language L, index every
    other language and classify L's templates. Returns {"overall": acc, "per_language": {lang: {acc, n}}}."""
    rows = _label_rows()
    langs = sorted({r[3] for r in rows})
    per, right, tot = {}, 0, 0
    for L in langs:
        train = [(t, i, s) for t, i, s, l in rows if l != L]
        test = [(t, i, s) for t, i, s, l in rows if l == L]
        if not train or not test:
            continue
        idx = NGramIndex(train)
        ok = sum(1 for t, i, s in test if idx.nearest(t, s)[0] == i)
        per[L] = {"acc": round(ok / len(test), 4), "n": len(test)}
        right += ok
        tot += len(test)
    return {"overall": round(right / tot, 4) if tot else 0.0, "per_language": per, "n_templates": tot}


# ----------------------------------------------------------------------------- layer 3: LLM templates
class TemplateClassifier:
    """One LLM call per DISTINCT normalised template; the answer is cached on disk. `calls` counts real calls."""

    def __init__(self, llm, cache_path: pathlib.Path = TEMPLATES_CACHE):
        self.llm, self.path, self.calls = llm, cache_path, 0
        self._lock = threading.Lock()
        try:
            self.cache = json.loads(cache_path.read_text())
        except Exception:  # noqa: BLE001
            self.cache = {}

    def classify(self, question: str, cost: Cost) -> Optional[str]:
        key = normalise(question)
        with self._lock:
            if key in self.cache:
                return self.cache[key] or None
            names = known_intents()
            reply = self.llm.complete(
                "Classify the architectural-drawing question into exactly one intent name from the list, "
                "or 'unknown'. Reply with the name only.",
                f"Intents: {', '.join(names)}\nQuestion: {question}", max_tokens=12)
            self.calls += 1
            cost.llm_calls += 1
            cost.tokens_in += reply.tokens_in
            cost.tokens_out += reply.tokens_out
            cost.usd += reply.usd
            name = reply.text.strip().strip("'\".` ").split()[0] if reply.text.strip() else "unknown"
            name = name if name in names else "unknown"
            self.cache[key] = name
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self.path.write_text(json.dumps(self.cache, ensure_ascii=False, indent=0))
            except OSError:
                pass
            return None if name == "unknown" else name


# ----------------------------------------------------------------------------- public
def route(question: str, path: str, *, classifier: Optional[TemplateClassifier] = None) -> Route:
    from evalkit import intents as I

    r = I.classify(question, path)
    if r.name != "unknown":
        return Route(r.name, dict(r.params), kind_of(r.name), r.lang, "regex")
    norm = normalise(question)
    idx = _index()
    if idx is not None and norm:
        name, sim = idx.nearest(norm, _src(path))
        if sim >= NGRAM_THRESHOLD:
            params = _params_from_quotes(name, question)
            return Route(name, params, kind_of(name), r.lang, "ngram")
    if classifier is not None:
        cost = Cost()
        name = classifier.classify(question, cost)
        if name:
            return Route(name, _params_from_quotes(name, question), kind_of(name), r.lang, "llm", cost)
        return Route("unknown", {}, "count", r.lang, "none", cost)
    return Route("unknown", {}, "count", r.lang, "none")
