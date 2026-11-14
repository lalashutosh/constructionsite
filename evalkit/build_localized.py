"""One-off builder: pairs each EN question with its "second language" neighbour (same path, same
answer+unit, immediately following row) and records normalized-template -> intent in
`evalkit/intents_localized.yaml`. Also writes `evalkit/out/intent_labels.jsonl` for every preview row.

Run with:  .venv/bin/python -m evalkit.build_localized

This only reads the dataset; it never writes dataset files. Re-run whenever intents.yaml changes.
"""
from __future__ import annotations

import collections
import json

import yaml

from evalkit.data import _iter_raw_rows, dataset_root
from evalkit.intents import LOCALIZED_PATH, _rules, guess_lang, normalize_template

NON_ENGLISH = {"fi", "de", "et", "da", "sv", "fr", "it"}


def _match_english(question: str, source: str) -> str | None:
    for rule in _rules():
        if rule.source is not None and rule.source != source:
            continue
        if rule.regex.search(question):
            return rule.name
    return None


def build(rows: list[dict] | None = None, *, write: bool = True) -> dict:
    """rows=None reads the real dataset (DATASET_ROOT); write=False skips touching
    evalkit/intents_localized.yaml and evalkit/out/intent_labels.jsonl (used by tests on a
    synthetic `rows` list so pairing logic can be verified without side effects)."""
    if rows is None:
        root = dataset_root()
        rows = list(_iter_raw_rows(root))
    groups: dict[str, list[dict]] = collections.OrderedDict()
    for r in rows:
        groups.setdefault(r["path"], []).append(r)

    localized_map: dict[str, str] = {}
    n_pairs_formed = 0

    for path, grp in groups.items():
        source = path.split("/")[1] if "/" in path else "unknown"
        for i, row in enumerate(grp):
            name = _match_english(row["question"], source)
            if not name:
                continue
            if i + 1 >= len(grp):
                continue
            nxt = grp[i + 1]
            if nxt.get("answer") != row.get("answer") or nxt.get("unit") != row.get("unit"):
                continue
            if guess_lang(nxt["question"]) == "en":
                continue  # two English phrasings in a row; not a translation pair
            key = f"{source}||{normalize_template(nxt['question'])}"
            if key not in localized_map:
                localized_map[key] = name
                n_pairs_formed += 1

    # Pairing coverage: of rows that look like a genuine translation (non-English, non-xx guess),
    # how many now resolve to an intent via direct English match OR the localized map.
    n_candidates = 0
    n_covered = 0
    for row in rows:
        lang = guess_lang(row["question"])
        if lang not in NON_ENGLISH:
            continue
        n_candidates += 1
        source = row["path"].split("/")[1] if "/" in row["path"] else "unknown"
        if _match_english(row["question"], source):
            n_covered += 1
            continue
        key = f"{source}||{normalize_template(row['question'])}"
        if key in localized_map:
            n_covered += 1

    pairing_pct = round(100.0 * n_covered / n_candidates, 1) if n_candidates else 0.0

    out = {
        "map": localized_map,
        "meta": {
            "n_pairs_formed": n_pairs_formed,
            "n_localized_candidates": n_candidates,
            "n_localized_covered": n_covered,
            "pairing_pct": pairing_pct,
        },
    }
    if not write:
        return out["meta"]

    LOCALIZED_PATH.write_text(yaml.safe_dump(out, allow_unicode=True, sort_keys=True), encoding="utf-8")

    # evalkit/out/intent_labels.jsonl for the whole preview set (clears intents.py's lru caches first
    # so the just-written localized map is picked up).
    from evalkit import intents as intents_mod
    intents_mod._localized_map.cache_clear()

    out_dir = __import__("pathlib").Path(__file__).resolve().parent / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "intent_labels.jsonl").open("w", encoding="utf-8") as f:
        for row in rows:
            intent = intents_mod.classify(row["question"], row["path"])
            f.write(json.dumps({
                "question": row["question"], "lang": intent.lang, "intent": intent.name, "path": row["path"],
            }, ensure_ascii=False) + "\n")

    return out["meta"]


if __name__ == "__main__":
    meta = build()
    print(f"pairing: {meta['n_localized_covered']}/{meta['n_localized_candidates']} "
          f"({meta['pairing_pct']}%) covered; {meta['n_pairs_formed']} template mappings written "
          f"to {LOCALIZED_PATH}")
