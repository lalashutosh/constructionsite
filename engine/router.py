"""Question router: `route(question, path) -> Route(intent, params, kind, lang, layer)`.

Layers, cheapest first, stop at the first confident hit:
  1. evalkit.intents.classify (regex + localized template table)            layer "regex"
  2. language-agnostic nearest template: char n-gram TF-IDF over evalkit/out/intent_labels.jsonl   layer "ngram"
     (kept only when the object-noun lexicon, engine/router_lexicon.yaml, is silent or agrees)
  2b. object-noun lexicon alone                                              layer "lexicon"
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


# ----------------------------------------------------------------------------- layer 2b: object-noun lexicon
LEXICON = pathlib.Path(__file__).with_name("router_lexicon.yaml")
_LEX: Optional["Lexicon"] = None


class Lexicon:
    """Hand-written multilingual object nouns + kind cues (engine/router_lexicon.yaml), not fitted to any question
    set. Covers the case where the template n-gram layer is weakest: a short paraphrase sits closer to a short
    template of the WRONG object ("how many doors are there" ~ "how many windows are drawn"). Abstains unless
    exactly one kind and one concept-to-intent mapping apply."""

    def __init__(self, path: pathlib.Path = LEXICON):
        import yaml
        d = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.kinds = [(k, re.compile(v, re.I)) for k, v in d["kind_cues"].items()]
        self.concepts = [(k, re.compile(v, re.I)) for k, v in d["concepts"].items()]
        self.table = d["intents"]

    def explicit_kind(self, q: str) -> Optional[str]:
        for k, rx in self.kinds:                      # area/length/volume cues beat the generic count cue
            if rx.search(q):
                return k
        return None

    def kind(self, q: str) -> str:
        return self.explicit_kind(q) or "count"

    _EXCL = re.compile(r"\b(without|except|excluding|not\s+counting|ohne|au(ss|ß)er|sans|hors|senza|esclus\w*|eccetto|"
                       r"lukuun\s+ottamatta|ilman|v\.a\.|välja\s+arvatud|uden|undtagen|utom|utan)\b[^.;?!]*", re.I)

    def winner(self, norm_q: str, source: str) -> Optional[str]:
        table = (self.table.get(source) or {}).get(self.kind(norm_q))
        if not table:
            return None
        norm_q = self._EXCL.sub(" ", norm_q)        # "... without balconies": the excluded noun is not the subject
        for name, rx in self.concepts:
            if rx.search(norm_q):
                return table.get(name)                # first (most specific) concept decides, or abstains
        return None


def _lexicon() -> Optional[Lexicon]:
    global _LEX
    with _INDEX_LOCK:
        if _LEX is None and LEXICON.exists():
            _LEX = Lexicon()
    return _LEX


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
    """Leave-one-language-out accuracy of layers 2+2b (n-gram, overridden by the lexicon) over distinct templates: for each language L, index every
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
        lex = _lexicon()                       # hand-written, not learned: no leakage across languages
        ok = 0
        for t, i, s in test:
            n = idx.nearest(t, s)[0]
            k = lex.winner(t, s) if lex is not None else None
            ok += int((n if (k is None or k == n) else k) == i)
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


# ----------------------------------------------------------------------------- complex questions
# Wording that turns a simple count/area into a different question. When a question is NOT a known dataset template
# and carries one of these, a fixed intent would answer the wrong question confidently ("average room area in
# apartment B" is not apartment B's net area), so it goes to the planner (or abstains when the LLM is off).
COMPLEX = re.compile(
    r"\b(average|mean|median|per\s+(room|apartment|floor)|each|which|largest|biggest|smallest|widest|longest|"
    r"more\s+(\w+\s+)?than|fewer\s+(\w+\s+)?than|less\s+(\w+\s+)?than|compared?|minus|difference|ratio|percent|%|"
    r"contain(s|ing)?|with\s+(a|an|no|at\s+least)|without\s+(a|an|any)|that\s+have|have\s+no|has\s+no|"
    r"and\s+(the\s+)?\w+\s+(in\s+total|together|combined)|in\s+total|combined|"
    r"durchschnitt|welche[rs]?|größte|grösste|mehr\s+als|moyenne|quel(le)?s?|plus\s+grand|plus\s+de|"
    r"media|quale|più\s+grande|keskimäär\w*|mikä|suurin)\b", re.I)
_TEMPLATES: Optional[set] = None


def _known_template(q: str) -> bool:
    global _TEMPLATES
    if _TEMPLATES is None:
        _TEMPLATES = {t for t, _, _, _ in _label_rows()}
    return normalise(q) in _TEMPLATES


def is_complex(q: str) -> bool:
    return bool(COMPLEX.search(unicodedata.normalize("NFKC", q))) and not _known_template(q)


# ----------------------------------------------------------------------------- public
def route(question: str, path: str, *, classifier: Optional[TemplateClassifier] = None) -> Route:
    from evalkit import intents as I

    r = I.classify(question, path)
    if is_complex(question):
        if classifier is not None:
            return Route("unknown", {}, "count", r.lang, "complex")      # planner drafts a query for it
        if r.name == "unknown":
            return Route("unknown", {}, "count", r.lang, "complex")
        # LLM off: keep the fixed intent but say the question may ask more than the template answers
        return Route(r.name, dict(r.params), kind_of(r.name), r.lang, "regex-complex")
    if r.name != "unknown":
        return Route(r.name, dict(r.params), kind_of(r.name), r.lang, "regex")
    norm = normalise(question)
    idx = _index()
    lex = _lexicon()
    kw_name = lex.winner(norm, _src(path)) if (lex is not None and norm) else None
    if idx is not None and norm:
        name, sim = idx.nearest(norm, _src(path))
        cue = lex.explicit_kind(norm) if lex is not None else None
        kind_ok = cue is None or cue == kind_of(name)  # "area of the kitchen" is not the kitchen count
        if sim >= NGRAM_THRESHOLD and kind_ok and (kw_name is None or kw_name == name):
            params = _params_from_quotes(name, question)
            return Route(name, params, kind_of(name), r.lang, "ngram")
    if kw_name is not None:
        return Route(kw_name, _params_from_quotes(kw_name, question), kind_of(kw_name), r.lang, "lexicon")
    if classifier is not None:
        cost = Cost()
        name = classifier.classify(question, cost)
        if name:
            return Route(name, _params_from_quotes(name, question), kind_of(name), r.lang, "llm", cost)
        return Route("unknown", {}, "count", r.lang, "none", cost)
    return Route("unknown", {}, "count", r.lang, "none")
