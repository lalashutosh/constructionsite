"""User element overrides: "this is not a door, it is a window". Stored per file sha256 in
cache/element_overrides/<sha>.json (atomic write, same style as engine/scale/sheet_scale.py load_answers/save_answers).

`apply(facts, sha)` returns a copy of the SheetFacts with the user's decisions applied BEFORE voting, so every count and
area recomputes. The facts cache (cache/pipeline) is never touched: overrides are applied on a copy after the cache
lookup, so an override takes effect on the very next question and the cached extraction stays pure. `overrides_hash`
fingerprints the active overrides (stamped into facts.extras) for any cache that keys answers.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import time
from typing import Any, Optional

from contracts.proof import Element, SheetFacts

ROOT = pathlib.Path(__file__).resolve().parents[1]
DIR = pathlib.Path(os.environ.get("PLUMB_CACHE_DIR", str(ROOT / "cache"))) / "element_overrides"

KINDS = ("door", "window", "opening", "fixture", "wall", "room", "stair", "not_element")
ROOM_SUBTYPES = ("bedroom", "kitchen", "living", "bathroom", "wc", "sauna", "storage", "hall", "balcony", "other")
ACTIONS = ("retype", "remove", "restore")
_SUBTYPE_ALIAS = {"hall": "hallway"}        # the extractor's own spelling for hall rooms

# which count intents an element of (kind, subtype) feeds (engine/count/rules.py)
_KIND_INTENTS = {"door": ["doors"], "window": ["windows"], "toilet": ["toilets"], "sink": ["sinks"],
                 "bath": ["showers_baths"], "bathtub": ["bathtubs", "showers_baths"], "shower": ["showers", "showers_baths"],
                 "washbasin": ["washbasins"], "stair": ["stairs"], "wall": ["wall_length"], "opening": ["openings"],
                 "fixture": ["fixtures"]}
_ROOM_INTENTS = {"bedroom": "bedrooms", "kitchen": "kitchens", "bathroom": "bathrooms", "wc": "wc_rooms",
                 "sauna": "saunas", "balcony": "balconies"}


def feeds(kind: str, subtype: Optional[str] = None) -> list[str]:
    if kind == "room":
        out = ["rooms", "total_area"]
        s = {"hallway": "hall", "living_room": "living"}.get(subtype or "", subtype or "")
        if s in _ROOM_INTENTS:
            out.insert(0, _ROOM_INTENTS[s])
        return out
    return list(_KIND_INTENTS.get(kind, []))


# ----------------------------------------------------------------------------------------------- storage
def _file(sha: str) -> pathlib.Path:
    return DIR / f"{sha}.json"


def load(sha: str) -> list[dict]:
    f = _file(sha)
    if f.exists():
        try:
            return list(json.loads(f.read_text()).get("overrides", []))
        except Exception:  # noqa: BLE001
            pass
    return []


def save(sha: str, records: list[dict]) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    f = _file(sha)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps({"overrides": records}))
    tmp.replace(f)


def overrides_hash(sha: str) -> str:
    recs = effective(load(sha))
    return hashlib.sha1(json.dumps(recs, sort_keys=True).encode()).hexdigest()[:12] if recs else ""


def validate(action: str, kind: Optional[str], subtype: Optional[str]) -> None:
    if action not in ACTIONS:
        raise ValueError(f"action must be one of {ACTIONS}")
    if action == "retype":
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}")
        if kind == "room" and subtype is not None and subtype not in ROOM_SUBTYPES:
            raise ValueError(f"room subtype must be one of {ROOM_SUBTYPES}")


def add(sha: str, element_id: str, action: str, kind: Optional[str] = None, subtype: Optional[str] = None) -> dict:
    validate(action, kind, subtype)
    rec: dict[str, Any] = {"element_id": element_id, "action": action, "at": time.time()}
    if action == "retype":
        rec["kind"] = kind
        if subtype:
            rec["subtype"] = subtype
    recs = load(sha)
    recs.append(rec)
    save(sha, recs)
    return rec


def undo(sha: str) -> Optional[dict]:
    recs = load(sha)
    if not recs:
        return None
    last = recs.pop()
    save(sha, recs)
    return last


def effective(records: list[dict]) -> dict[str, dict]:
    """Last record per element wins; `restore` cancels the element's override."""
    out: dict[str, dict] = {}
    for r in records:
        if r.get("action") == "restore":
            out.pop(r["element_id"], None)
        else:
            out[r["element_id"]] = r
    return out


# ----------------------------------------------------------------------------------------------- apply
def apply(facts: SheetFacts, sha: str, records: Optional[list[dict]] = None) -> SheetFacts:
    eff = effective(load(sha) if records is None else records)
    if not eff:
        return facts
    out = facts.model_copy(deep=True)
    removed: list[dict] = []
    delta: dict[str, int] = {}                       # per element kind: how many the user added (+) or took away (-)
    keep: list[Element] = []
    origs: dict[str, tuple] = {}
    for e in out.elements:
        r = eff.get(e.id)
        if r is not None:
            origs[e.id] = (e.kind, e.subtype)
        if r is None:
            keep.append(e)
            continue
        orig = {"id": e.id, "from_kind": e.kind, "from_subtype": e.subtype}
        remove = r["action"] == "remove" or (r["action"] == "retype" and r.get("kind") == "not_element")
        if remove:
            removed.append({**orig, "element": e.model_dump(mode="json"), "at": r.get("at")})
            delta[e.kind] = delta.get(e.kind, 0) - 1
            continue
        new_kind = r["kind"]
        new_sub = r.get("subtype")
        if new_kind == "room" and new_sub:
            new_sub = _SUBTYPE_ALIAS.get(new_sub, new_sub)
        if new_kind != "room" and not new_sub:
            new_sub = None
        if (new_kind, new_sub) != (e.kind, e.subtype):
            if new_kind != e.kind:
                delta[e.kind] = delta.get(e.kind, 0) - 1
                delta[new_kind] = delta.get(new_kind, 0) + 1
        e.kind = new_kind
        e.subtype = new_sub if new_kind == "room" or new_sub else None
        e.conf = 1.0
        e.attrs = dict(e.attrs)
        e.attrs["user_override"] = {"from_kind": orig["from_kind"], "from_subtype": orig["from_subtype"], "tag": "chosen"}
        keep.append(e)
    out.elements = keep
    # the icon counters read per-run counts from extras["cnn_runs"][kind]: shift them by what the user changed
    runs = out.extras.get("cnn_runs")
    if isinstance(runs, dict):
        runs = {k: list(v) for k, v in runs.items()}
        for k, d in delta.items():
            if d:
                runs[k] = [max(0, int(x) + d) for x in runs.get(k, [])] or runs.get(k, [])
        out.extras["cnn_runs"] = runs
    out.extras["removed_by_user"] = removed
    out.extras["overrides_hash"] = overrides_hash(sha) if records is None else \
        hashlib.sha1(json.dumps(eff, sort_keys=True).encode()).hexdigest()[:12]
    out.extras["user_overrides"] = [{"element_id": k, **{x: v for x, v in r.items() if x != "element_id"},
                                     **({"from_kind": origs[k][0], "from_subtype": origs[k][1]} if k in origs else {})}
                                    for k, r in eff.items()]
    return out


def annotate(po, facts: SheetFacts) -> None:
    """Receipt: any evidence element the user changed says so (note + Assumption tagged chosen); removed elements that
    would have fed this answer are listed. Mutates the ProofObject in place."""
    from contracts.proof import Assumption, Tag
    notes = po.notes
    seen: set[str] = set()
    for e in po.evidence:
        uo = e.attrs.get("user_override")
        if not uo or e.id in seen:
            continue
        seen.add(e.id)
        src = f"{uo.get('from_kind')}" + (f" ({uo.get('from_subtype')})" if uo.get("from_subtype") else "")
        dst = f"{e.kind}" + (f" ({e.subtype})" if e.subtype else "")
        notes.append(f"you changed element {e.id} from {src} to {dst}")
        po.assumptions.append(Assumption(key=f"user_element:{e.id}", value=dst, tag=Tag.chosen,
                                         source=f"user changed {e.id} from {src}"))
    for r in facts.extras.get("removed_by_user", []):
        if po.intent and po.intent in feeds(r["from_kind"], r.get("from_subtype")):
            src = f"{r['from_kind']}" + (f" ({r['from_subtype']})" if r.get("from_subtype") else "")
            notes.append(f"you removed element {r['id']} (was {src})")
            po.assumptions.append(Assumption(key=f"user_element:{r['id']}", value="removed", tag=Tag.chosen,
                                             source=f"user removed {r['id']} ({src})"))
    # retyped elements that are not pinned as evidence here still change this count (gained or lost)
    for u in facts.extras.get("user_overrides", []):
        if u["element_id"] in seen or u.get("action") != "retype" or not po.intent or u.get("kind") == "not_element":
            continue
        new = f"{u['kind']}" + (f" ({u['subtype']})" if u.get("subtype") else "")
        old = f"{u.get('from_kind')}" + (f" ({u['from_subtype']})" if u.get("from_subtype") else "")
        gained = po.intent in feeds(u["kind"], u.get("subtype"))
        lost = po.intent in feeds(u.get("from_kind") or "", u.get("from_subtype"))
        if gained != lost:
            notes.append(f"you changed element {u['element_id']} from {old} to {new} "
                         f"({'counted here now' if gained else 'no longer counted here'})")
            po.assumptions.append(Assumption(key=f"user_element:{u['element_id']}", value=new, tag=Tag.chosen,
                                             source=f"user changed {u['element_id']} from {old}"))
