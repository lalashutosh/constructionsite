"""A folder of drawings -> one building: which files are floor plans, which floor each one shows, in what order.

    organise(files, geometry_of, llm=None) -> {"floors": [...], "other": [...], "notes": [...]}

files: [{"path": <api path>, "name": <original relative name from the browser, e.g. 'house/2_floor.png'>}]
geometry_of(path) -> the /api/geometry dict (scan check included; cached by sha256, so cheap after the first time).

Floor level, first source that answers:
  1. the file / folder name ("kellari", "basement", "1. kerros", "EG", "OG 2", "plan-02", "level 3", "2nd floor" ...)
  2. (LLM on) a vision model reads the sheet title (fixed JSON form; it reads a label, it never measures)
  3. unknown -> kept in upload order after the known ones
Each floor says where its level came from. Non-plan sheets (sections, elevations, details, photos) are listed
separately with what the scan check found, never stacked as floors.
"""
from __future__ import annotations

import json
import re
from typing import Callable, Optional

# (regex, level) in order; level 0 = ground floor, -1 = basement, 99 = roof/attic (sorted last)
NAMED = [
    (r"\b(basement|cellar|kellari|k[äa]llare|keller|untergeschoss|sous-sol|seminterrato|kelder|ug|kg)\b", -1),
    (r"\b(ground\s*floor|ground|gf|maantasokerros|bottenv[åa]ning|erdgeschoss|rez[- ]de[- ]chauss[ée]e|piano\s*terra|eg|rdc)\b", 0),
    (r"\b(attic|loft|roof|ullakko|vind|vinde|dachgeschoss|dg|sottotetto|combles)\b", 99),
]
NUMBERED = [
    r"\b(?:floor|level|storey|story|lvl|etage|stock|geschoss|kerros|krs|v[åa]ning|plan|piano|korrus|etasje|plan-)\s*[-_.]?\s*(\d{1,2})\b",
    r"\b(\d{1,2})\s*[-_.]?\s*(?:st|nd|rd|th)?\s*(?:floor|level|storey|story|kerros|krs|korrus|v[åa]ning|etage|og|obergeschoss|piano)\b",
    r"\bog\s*(\d{1,2})\b",
    r"\b(\d{1,2})\.?\s*og\b",
]
ORD = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5}

LEVEL_SYSTEM = (
    "You read the title of an architectural drawing. Reply with JSON only: "
    '{"level": <integer floor number, 0 = ground floor, -1 = basement, null if not stated>, '
    '"label": "<the floor name exactly as printed, or empty>"}. Never guess a level that is not printed.'
)


def level_from_name(name: str) -> Optional[tuple[int, str]]:
    n = re.sub(r"[_]+", " ", name.lower())
    for rx, lv in NAMED:
        m = re.search(rx, n)
        if m:
            return lv, m.group(0)
    for rx in NUMBERED:
        m = re.search(rx, n)
        if m:
            return int(m.group(1)), m.group(0)
    for w, v in ORD.items():
        if re.search(rf"\b{w}\s+(floor|storey|level)\b", n):
            return v, f"{w} floor"
    return None


def _level_from_llm(llm, image_png: bytes) -> Optional[tuple[int, str]]:
    try:
        r = llm.complete_vision(LEVEL_SYSTEM, "What floor does this drawing show?", image_png, max_tokens=120)
        m = re.search(r"\{.*\}", r.text or "", re.S)
        d = json.loads(m.group(0)) if m else {}
        if isinstance(d.get("level"), int):
            return d["level"], str(d.get("label") or "")
    except Exception:  # noqa: BLE001
        return None
    return None


DOC_TYPES = ("floor_plan", "foundation_plan", "enlarged_plan", "site_plan", "roof_plan", "reflected_ceiling_plan", "section", "elevation", "detail",
             "schedule", "render_3d", "photo", "bim_model", "cad_drawing", "specification", "other")
SHEET = re.compile(r"\b([A-Z]{1,2})[- ]?(\d{3})\b")
NAME_RULES = [  # filename / title words -> doc type (fallback when the LLM is off)
    (r"site\s*plan|asemapiirros|lageplan|situationsplan", "site_plan"),
    (r"roof\s*plan|kattopiirros|dachaufsicht", "roof_plan"),
    (r"ceiling|rcp\b", "reflected_ceiling_plan"),
    (r"floor\s*plan|plan\b|pohjapiirros|grundriss|kerros|plantegning|basement|kellari", "floor_plan"),
    (r"section|leikkaus|schnitt|coupe", "section"),
    (r"elevation|julkisivu|ansicht|fa[cç]ade", "elevation"),
    (r"detail|details|wall\s*types?|glazing", "detail"),
    (r"schedule|luettelo|liste", "schedule"),
    (r"3d\s*view|perspective|render|axon", "render_3d"),
]

CLASSIFY_SYSTEM = (
    "You organise the drawings of one building project. For EVERY file in the manifest decide what it is, using its "
    "name, the title-block text and the machine checks given. Think carefully: a sheet called 'Floor & Site Plan' that "
    "the scan check sees as a site plan is a site plan sheet; a '3D View' is a render, never a floor; sheet prefixes "
    "A=architectural, S=structural, M/E/P=services; a .ifc file is a BIM model; .dwg is a CAD drawing. Floor plans need "
    "a level. Titles must use only words from the file name or title-block text; never add words. 0 = ground/first floor as printed (use the printed floor names), -1 = basement, null if not stated. "
    "Footing / foundation plans are foundation_plan, partial or enlarged plans are enlarged_plan: neither is a storey. "
    "Several plans of the SAME storey (revisions, phases, dates) are alternatives, not separate floors: give them the "
    "same level and a \"version\" note (date or phase). "
    'Reply with JSON only: {"files": [{"i": <index>, "doc_type": one of ' + "|".join(DOC_TYPES) + ', "discipline": '
    '"architectural|structural|services|interiors|other", "sheet": "<sheet number or empty>", "title": "<short title>", '
    '"level": <int or null>, "level_label": "<floor name as printed or empty>", "why": "<= 15 words"}], '
    '"building": "<what the project is, <= 12 words>"}'
)


def signals(path_abs: str, name: str) -> dict:
    """Cheap per-file facts for the classifier: title-block text (vector PDF), IFC storeys, sheet number."""
    out = {"ext": name.rsplit(".", 1)[-1].lower() if "." in name else ""}
    m = SHEET.search(name.upper())
    if m:
        out["sheet"] = f"{m.group(1)}-{m.group(2)}"
    try:
        if out["ext"] == "pdf":
            import fitz
            with fitz.open(path_abs) as doc:
                out["pages"] = len(doc)
                t = " ".join(doc[0].get_text().split())
                out["text"] = t[:500]
        elif out["ext"] == "ifc":
            import os
            if os.path.getsize(path_abs) > 60 * 1024 * 1024:     # huge models: name only, never block the folder
                out["note"] = "large IFC model, storeys not read"
                return out
            import ifcopenshell
            m = ifcopenshell.open(path_abs)
            out["storeys"] = [st.Name for st in m.by_type("IfcBuildingStorey")][:20]
    except Exception:  # noqa: BLE001
        pass
    return out


def _sig_worker(args):
    return signals(*args)


def signals_isolated(items: list[tuple[str, str]], timeout_s: float = 60.0) -> list[dict]:
    """signals() for many files in WORKER PROCESSES: PyMuPDF / IfcOpenShell are native and not thread-safe, and one
    malformed upload must never take the API process down (it did: folder upload killed the server). A crash or a
    hang only loses that file, which is then listed with an error."""
    import concurrent.futures as cf
    import multiprocessing as mp
    out: list[dict] = []
    ctx = mp.get_context("spawn")
    with cf.ProcessPoolExecutor(max_workers=4, mp_context=ctx) as ex:
        futs = [ex.submit(_sig_worker, it) for it in items]
        for (path, name), fu in zip(items, futs):
            ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
            try:
                out.append(fu.result(timeout=timeout_s))
            except cf.TimeoutError:
                out.append({"ext": ext, "error": "timed out reading the file"})
            except Exception as e:  # noqa: BLE001  (BrokenProcessPool after a native crash, parse errors ...)
                out.append({"ext": ext, "error": f"could not read the file ({type(e).__name__})"})
    return out


def classify(files: list[dict], sig: list[dict], scan: list[list[str]], llm=None) -> tuple[list[dict], str, str]:
    """Per-file {doc_type, discipline, sheet, title, level, level_label, why, source}; (list, building, method)."""
    out = []
    for f, sg, sc in zip(files, sig, scan):
        name = f.get("name") or f["path"]
        nm, body = name.lower(), sg.get("text", "").lower()
        dt = "bim_model" if sg.get("ext") == "ifc" else "cad_drawing" if sg.get("ext") == "dwg" else None
        if dt is None:          # the file name is the author's label; title-block text only if the name is silent
            dt = next((t for rx, t in NAME_RULES if re.search(rx, nm)), None) or \
                next((t for rx, t in NAME_RULES if re.search(rx, body[:200])), None)
        if dt is None and sc:
            dt = sc[0] if sc[0] in DOC_TYPES else "other"
        lv = level_from_name(name) if dt == "floor_plan" else None
        out.append({"doc_type": dt or "other", "discipline": "", "sheet": sg.get("sheet", ""), "title": name.rsplit("/", 1)[-1],
                    "level": lv[0] if lv else None, "level_label": lv[1] if lv else "", "why": "name rules",
                    "source": "rules"})
    if llm is None:
        return out, "", "rules (LLM off)"
    manifest = [{"i": i, "name": f.get("name") or f["path"], **{k: v for k, v in sg.items() if k != "pages"},
                 "scan_check": sc} for i, (f, sg, sc) in enumerate(zip(files, sig, scan))]
    batches = [manifest[k:k + 12] for k in range(0, len(manifest), 12)]
    usd, parsed, building = 0.0, 0, ""

    def one(batch):
        r = llm.complete(CLASSIFY_SYSTEM, json.dumps(batch, ensure_ascii=False)[:20000], max_tokens=16000)
        return r

    try:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=3) as ex:
            replies = list(ex.map(one, batches))
    except Exception as e:  # noqa: BLE001
        return out, "", f"rules (LLM failed: {type(e).__name__})"
    for r in replies:
        usd += r.usd
        text = r.text or ""
        mb = re.search(r'"building"\s*:\s*"([^"]*)"', text)
        building = building or (mb.group(1) if mb else "")
        for obj in re.findall(r'\{[^{}]*"i"\s*:\s*\d+[^{}]*\}', text):    # every complete entry, even if cut off
            try:
                row = json.loads(obj)
            except json.JSONDecodeError:
                continue
            i = row.get("i")
            if isinstance(i, int) and 0 <= i < len(out) and row.get("doc_type") in DOC_TYPES:
                lvl = row.get("level") if isinstance(row.get("level"), int) else None
                out[i].update(doc_type=row["doc_type"], discipline=str(row.get("discipline", "")),
                              sheet=str(row.get("sheet") or out[i]["sheet"]), title=str(row.get("title") or out[i]["title"]),
                              level=lvl if row["doc_type"] == "floor_plan" else None,
                              level_label=str(row.get("level_label") or ""), why=str(row.get("why", ""))[:120],
                              version=str(row.get("version") or ""),
                              source="AI (reasoning model) + title block + scan check")
                parsed += 1
    return out, building[:120], f"reasoning model ({getattr(llm, 'kind', 'llm')}): {parsed}/{len(out)} files, ${usd:.4f}"


def organise(files: list[dict], geometry_of: Callable[[str], dict], llm=None,
             image_of: Optional[Callable[[str], bytes]] = None, abs_of: Optional[Callable[[str], str]] = None,
             thinker=None) -> dict:
    """thinker: an LLM with reasoning ON for the folder-level classification (one call for all files)."""
    if thinker is not None or abs_of is not None:
        return _organise_smart(files, geometry_of, thinker, abs_of or (lambda p: p))
    return _organise_simple(files, geometry_of, llm, image_of)


def _organise_smart(files, geometry_of, thinker, abs_of) -> dict:
    import os
    missing = [f for f in files if not os.path.exists(abs_of(f["path"]))]
    files = [f for f in files if f not in missing]
    if not files:
        return {"building": "", "method": "no readable files", "floors": [], "alternatives": [],
                "other": [{"path": f["path"], "name": f.get("name") or f["path"], "doc_type": "missing",
                           "why": "file not found", "display_label": f.get("name") or f["path"]} for f in missing],
                "groups": {"missing": [f.get("name") or f["path"] for f in missing]} if missing else {},
                "notes": [f"{len(missing)} file(s) not found"] if missing else ["empty folder"]}
    out = _organise_present(files, geometry_of, thinker, abs_of)
    for f in missing:
        out["other"].append({"path": f["path"], "name": f.get("name") or f["path"], "doc_type": "missing",
                             "why": "file not found", "display_label": f.get("name") or f["path"]})
        out["groups"].setdefault("missing", []).append(f.get("name") or f["path"])
    if missing:
        out["notes"].append(f"{len(missing)} file(s) not found")
    return out


def _organise_present(files, geometry_of, thinker, abs_of) -> dict:
    # Classification needs only cheap signals (name, title-block text, IFC storeys). The 3D geometry + scan check
    # (CNN + 2 AI reviews per file) is built later, only for the floors the user opens: building it for every file
    # here made big folders run for minutes and time out. A scan check already cached for a file is still used.
    sig = signals_isolated([(abs_of(f["path"]), f.get("name") or f["path"]) for f in files])
    scan = []
    for f in files:
        types = []
        try:
            g = geometry_of(f["path"], cached_only=True)
            if g:
                types = [v.get("type") for v in (g.get("check") or {}).get("views") or [] if v.get("type")]
        except TypeError:
            pass                                       # geometry_of without cached_only (tests): skip
        except Exception:  # noqa: BLE001
            types = []
        scan.append(types)
    cls, building, method = classify(files, sig, scan, thinker)
    floors, other = [], []
    for i, (f, c) in enumerate(zip(files, cls)):
        row = {"path": f["path"], "name": f.get("name") or f["path"], **c, "scan_check": scan[i],
               "ifc_storeys": sig[i].get("storeys", [])}
        (floors if c["doc_type"] == "floor_plan" else other).append({**row, "order": i})
    # only DIFFERENT storeys stack; several plans of one storey (or of an unknown one) are alternatives
    by_level: dict = {}
    for x in floors:
        by_level.setdefault(x["level"], []).append(x)
    notes, ordered, alternatives = [], [], []
    for lv in sorted(k for k in by_level if k is not None):
        group = sorted(by_level[lv], key=lambda x: (x.get("version") or x["name"]))
        ordered.append(group[-1])                       # newest version/phase stands for the storey
        for alt in group[:-1]:
            alternatives.append({**alt, "alternative_of": group[-1]["name"]})
        if len(group) > 1:
            notes.append(f"{len(group)} plans show the same storey (level {lv}): the newest is used, the rest are alternatives")
    unknown = by_level.get(None, [])
    if unknown and not ordered:
        ordered.append(unknown[-1])                    # one plan to show; the others are alternatives
        alternatives += [{**x, "alternative_of": unknown[-1]["name"]} for x in unknown[:-1]]
        notes.append(f"{len(unknown)} plans without a storey number: shown one at a time (switch in the explorer), not stacked")
    elif unknown:
        alternatives += [{**x, "alternative_of": None} for x in unknown]
        notes.append(f"{len(unknown)} plan(s) without a storey number kept out of the stack")
    for x in alternatives:
        x.pop("order", None)
    for k, x in enumerate(ordered):
        x["stack_index"] = k
        x["level_source"] = "title block / file name (AI)" if x["source"].startswith("AI") and x["level"] is not None \
            else ("file name" if x["level"] is not None else "upload order")
    for x in ordered + other:
        x.pop("order", None)
    groups: dict[str, list[str]] = {}
    for x in other:
        groups.setdefault(x["doc_type"], []).append(x["name"])
    for x in ordered:
        x["display_label"] = x["level_label"] or (f"Level {x['level']}" if x["level"] is not None else x["title"])
    for x in other + alternatives:
        x["display_label"] = x.get("title") or x["name"]
    return {"building": building, "method": method, "floors": ordered, "alternatives": alternatives, "other": other,
            "groups": groups, "notes": notes}


def _organise_simple(files: list[dict], geometry_of: Callable[[str], dict], llm=None,
                     image_of: Optional[Callable[[str], bytes]] = None) -> dict:
    floors, other, notes = [], [], []
    for i, f in enumerate(files):
        name = f.get("name") or f["path"].rsplit("/", 1)[-1]
        try:
            g = geometry_of(f["path"])
        except Exception as e:  # noqa: BLE001
            other.append({"path": f["path"], "name": name, "type": "unreadable", "why": f"{type(e).__name__}"})
            continue
        views = (g.get("check") or {}).get("views") or []
        types = [v.get("type") for v in views if v.get("type")]
        is_plan = (not types) or ("floor_plan" in types)
        if not is_plan:
            other.append({"path": f["path"], "name": name, "type": types[0] if types else "other",
                          "why": f"scan check: {', '.join(sorted(set(types)))}"})
            continue
        lv = level_from_name(name)
        src = "file name" if lv else None
        if lv is None and llm is not None and image_of is not None:
            lv = _level_from_llm(llm, image_of(f["path"]))
            src = "sheet title (read by AI)" if lv else None
        floors.append({"path": f["path"], "name": name, "level": lv[0] if lv else None,
                       "level_label": lv[1] if lv else "", "level_source": src or "upload order",
                       "walls": len(g.get("walls") or []), "order": i})
    known = sorted([x for x in floors if x["level"] is not None], key=lambda x: (x["level"], x["order"]))
    unknown = [x for x in floors if x["level"] is None]
    if unknown:
        notes.append(f"{len(unknown)} floor plan(s) have no readable floor number; kept in upload order on top")
    lv_seen = {}
    for x in known:
        lv_seen.setdefault(x["level"], []).append(x["name"])
    for lv, names in lv_seen.items():
        if len(names) > 1:
            notes.append(f"{len(names)} files claim floor {lv}: {', '.join(names)} (alternatives or duplicates?)")
    ordered = known + unknown
    for k, x in enumerate(ordered):
        x["stack_index"] = k
        x.pop("order", None)
    return {"floors": ordered, "other": other, "notes": notes}
