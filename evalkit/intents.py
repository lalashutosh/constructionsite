"""Question -> Intent classification. Others import `classify`; do not change its signature.

English intents are regexes in `evalkit/intents.yaml` with named capture groups -> Intent.params.
Non-English rows are mapped by exact (digit/quote-normalised) template lookup in
`evalkit/intents_localized.yaml`, built once from the dataset's EN-then-other-language pairing
(see `build_localized_mapping` / `evalkit/_build_localized.py`, run offline, not at import time).
"""
from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Optional

import yaml

_HERE = pathlib.Path(__file__).resolve().parent
PATTERNS_PATH = _HERE / "intents.yaml"
LOCALIZED_PATH = _HERE / "intents_localized.yaml"

# ISO codes we expect to see in the preview dataset, plus "xx" for unrecognised.
# Stopwords mined by hand from docs/recon.md question templates (digits/quotes already generic).
_LANG_STOPWORDS: dict[str, set[str]] = {
    "fi": {"kuinka", "monta", "pohjapiirustuksessa", "pohjapiirustukseen", "ikkunaa", "ovea", "kerrosta",
           "wc-istuinta", "saunaa", "keittiötä", "makuuhuonetta", "parveketta", "esitetty", "piirretty"},
    "et": {"mitu", "kui", "suur", "ruumi", "ruumide", "korrusel", "korruse", "plaanil", "netopõrandapind",
           "näidatud", "seina", "ust", "akent", "posti"},
    "da": {"hvor", "mange", "hvad", "er", "vist", "plantegningen", "nettoarealet", "rummet", "vægge", "søjler",
           "dæk", "etage", "sal"},
    "sv": {"hur", "många", "är", "rum", "visas", "planritningen", "våning"},
    "de": {"wie", "viele", "sind", "ist", "grundriss", "eingezeichnet", "räume", "räumen", "wohnung",
           "geschoss", "bezeichnung", "badewannen", "türen", "fenster", "lavabos", "wc"},
    "fr": {"combien", "quelle", "quels", "sont", "dessinées", "dessinés", "pièce", "pièces", "étage", "cet",
           "appartements", "fenêtres", "portes", "baignoires", "lavabos", "désignation"},
    "it": {"quanti", "quante", "quale", "qual", "sono", "pianta", "locali", "piano", "finestre", "porte",
           "vasche", "lavabi", "denominazione", "disegnate", "disegnati"},
    "en": {"how", "many", "what", "is", "are", "the", "shown", "drawn", "total", "floor", "plan", "this",
           "room", "rooms", "doors", "windows"},
}


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[^\W\d_]+", text.lower(), flags=re.UNICODE))


def guess_lang(question: str) -> str:
    """Small stopword/character heuristic. Returns en/fi/de/et/da/sv/fr/it, or xx if nothing matches."""
    tokens = _tokenize(question)
    if not tokens:
        return "xx"
    best_lang, best_score = "xx", 0
    # Check non-English languages first so a handful of shared words (e.g. "wc") don't win over "en".
    order = [l for l in _LANG_STOPWORDS if l != "en"] + ["en"]
    for lang in order:
        score = len(tokens & _LANG_STOPWORDS[lang])
        if score > best_score:
            best_score, best_lang = score, lang
    return best_lang if best_score > 0 else "xx"


@dataclass
class Intent:
    name: str
    params: dict[str, Any] = field(default_factory=dict)
    lang: str = "xx"


@dataclass
class _Rule:
    name: str
    kind: str
    source: Optional[str]
    regex: re.Pattern


def _normalize_template(question: str) -> str:
    """Digit/quote-normalised template key used to look up localized rows and to dedupe recon templates."""
    q = question.strip().lower()
    q = re.sub(r"\d+([.,]\d+)?", "#", q)
    q = re.sub(r"['‘’“”«»„‚][^'‘’“”«»„‚]*['‘’“”«»„‚]", "#q#", q)
    q = re.sub(r"\s+", " ", q)
    return q


@lru_cache(maxsize=1)
def _rules() -> list[_Rule]:
    data = yaml.safe_load(PATTERNS_PATH.read_text(encoding="utf-8")) or {}
    rules = []
    for item in data.get("intents", []):
        rules.append(_Rule(
            name=item["name"], kind=item.get("kind", "count"), source=item.get("source"),
            regex=re.compile(item["pattern"], re.IGNORECASE),
        ))
    return rules


@lru_cache(maxsize=1)
def _localized_map() -> dict[str, str]:
    """{"source||normalized_template": intent_name}. Empty dict if the file hasn't been generated yet."""
    if not LOCALIZED_PATH.exists():
        return {}
    data = yaml.safe_load(LOCALIZED_PATH.read_text(encoding="utf-8")) or {}
    return dict(data.get("map", {}))


def classify(question: str, path: str) -> Intent:
    """Public API. `path` is the questions.jsonl path (relative to DATASET_ROOT); unknown -> Intent("unknown")."""
    parts = path.split("/")
    source = parts[1] if len(parts) > 1 else None
    lang = guess_lang(question)

    for rule in _rules():
        if rule.source is not None and rule.source != source:
            continue
        m = rule.regex.search(question)
        if m:
            return Intent(name=rule.name, params=m.groupdict(), lang=lang)

    key = f"{source}||{_normalize_template(question)}"
    name = _localized_map().get(key)
    if name:
        return Intent(name=name, params={}, lang=lang)

    return Intent(name="unknown", params={}, lang=lang)


def normalize_template(question: str) -> str:
    """Exposed for the localized-mapping builder and tests."""
    return _normalize_template(question)
