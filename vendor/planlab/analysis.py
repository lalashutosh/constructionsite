import math, random, json, itertools
from collections import Counter, defaultdict
import networkx as nx
from planlab import load, build_graph

DEFAULTS = dict(min_leaf_w=0.80, kitchen_max=12.0, exit_max=20.0, n_personas=3000, seed=7,
                mobility_mix={"walker": 0.80, "stroller": 0.10, "wheelchair": 0.10},
                mobility_need={"walker": 0.65, "stroller": 0.75, "wheelchair": 0.85},  # min door leaf width, assumed
                ground_floor_scenario=True)

def dedupe_doors(plan):
    uniq, dups = [], []
    for d in plan["doors"]:
        m = next((u for u in uniq if math.dist(u["mid"], d["mid"]) < 0.15), None)
        (dups if m else uniq).append(d)
    return uniq, dups

def unit_entrance(plan, G, u):
    for d in plan["doors"]:
        a = next((r for r in plan["rooms"] if r["id"] == d["a"]), None)
        b = next((r for r in plan["rooms"] if r["id"] == d["b"]), None)
        ua = a["unit"] if a else None; ub = b["unit"] if b else None
        if (ua == u) != (ub == u):
            inside = a if ua == u else b
            return inside["id"], d
    return None, None

def analyze(dxf, **kw):
    P = {**DEFAULTS, **kw}
    plan = load(dxf); G = build_graph(plan)
    rooms = {r["id"]: r for r in plan["rooms"]}
    uniq, dups = dedupe_doors(plan)
    findings = []
    def add(rule, sev, title, why, rooms_=(), doors_=(), at=None, unit=None):
        findings.append(dict(n=len(findings) + 1, rule=rule, severity=sev, title=title, why=why,
                             rooms=list(rooms_), doors=list(doors_), at=at, unit=unit))
    if dups:
        add("DUPLICATE_DOOR_ENTITIES", "data", f"{len(dups)} door symbols are stacked on top of another door",
            f"{len(plan['doors'])} door symbols are drawn but only {len(uniq)} are physically distinct; a takeoff that counts symbols over-counts by {len(dups)}.",
            doors_=[d["idx"] for d in dups], at=dups[0]["mid"])
    # swing clashes between distinct doors
    for d1, d2 in itertools.combinations(uniq, 2):
        a = d1["sector"].intersection(d2["sector"]).area
        if a > 0.05:
            add("DOOR_SWING_CLASH", "high", "Two door swings overlap", f"Swings of doors {d1['idx']} and {d2['idx']} overlap by {a:.2f} m².",
                rooms_=[d1["a"], d1["b"]], doors_=[d1["idx"], d2["idx"]], at=d1["mid"])
    per_unit = {}
    rng = random.Random(P["seed"])
    for u, _ in enumerate(plan["units"]):
        ur = [r for r in plan["rooms"] if r["unit"] == u]
        if not ur: continue
        e_room, e_door = unit_entrance(plan, G, u)
        if not e_room: continue
        H = nx.Graph()
        for a, b, d in G.edges(data=True):
            if a in rooms and b in rooms and rooms[a]["unit"] == u and rooms[b]["unit"] == u:
                m = d["mid"]; ca, cb = rooms[a]["centroid"], rooms[b]["centroid"]
                H.add_edge(a, b, weight=math.dist(ca, m) + math.dist(m, cb), door=d["door"], width=d["width"])
        for r in ur: H.add_node(r["id"])
        lab = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[u] if u < 26 else str(u)
        path_to = {}
        for r in ur:
            if nx.has_path(H, e_room, r["id"]):
                path_to[r["id"]] = nx.shortest_path(H, e_room, r["id"], weight="weight")
        unreachable = [r["id"] for r in ur if r["id"] not in path_to]
        for rid in unreachable:
            add("UNREACHABLE", "high", f"Room {rid} cannot be reached from the entrance", "No door chain connects it to the apartment entrance.", [rid], at=rooms[rid]["centroid"], unit=lab)
        plen = lambda p: sum(H[p[i]][p[i + 1]]["weight"] for i in range(len(p) - 1))
        for rid, p in path_to.items():
            r = rooms[rid]; mid = p[:-1]                  # rooms passed through (incl. entrance room)
            through = [x for x in mid if rooms[x]["type"] == "room"]
            if r["type"] == "room" and through:
                add("WALK_THROUGH_ROOM", "high", f"Room {rid} is only reachable through room {through[0]}",
                    f"From the entrance you must cross {', '.join(through)} ({rooms[through[0]]['name']}) to reach {rid}. Privacy and noise problem; also counts as a bedroom without its own access.",
                    [rid] + through, at=r["centroid"], unit=lab)
            if r["type"] in ("bath", "wc") and through:
                add("WET_ROOM_THROUGH_ROOM", "high", f"Bathroom {rid} is only reachable through bedroom {through[0]}", "Guests or other residents must cross a private room to reach the bathroom.", [rid] + through, at=r["centroid"], unit=lab)
            if r["type"] == "kitchen":
                L = plen(p) + math.dist(rooms[e_room]["centroid"], e_door["mid"])
                if L > P["kitchen_max"]:
                    add("KITCHEN_FAR_FROM_ENTRANCE", "medium", f"Kitchen {rid} is {L:.1f} m from the entrance", f"Carrying groceries means walking {L:.1f} m through {len(p)} rooms.", p, at=r["centroid"], unit=lab)
                if any(rooms[x]["type"] == "room" for x in p[:-1]):
                    add("KITCHEN_THROUGH_ROOM", "high", f"Kitchen {rid} is only reachable through a bedroom", "", p, at=r["centroid"], unit=lab)
        # wet room opening straight into kitchen
        for a, b, d in H.edges(data=True):
            ta, tb = rooms[a]["type"], rooms[b]["type"]
            if {ta, tb} & {"bath", "wc"} and "kitchen" in (ta, tb):
                add("WET_ROOM_OFF_KITCHEN", "medium", f"Bathroom {a if ta in ('bath','wc') else b} opens directly into the kitchen", "Hygiene and privacy problem.", [a, b], doors_=[d["door"]], at=d.get("mid"), unit=lab)
        # exit distances
        dist_exit = {r["id"]: (plen(path_to[r["id"]]) + math.dist(rooms[e_room]["centroid"], e_door["mid"])) for r in ur if r["id"] in path_to and r["type"] != "balcony"}
        far = max(dist_exit, key=dist_exit.get) if dist_exit else None
        if far and dist_exit[far] > P["exit_max"]:
            add("LONG_EXIT_PATH", "medium", f"Room {far} is {dist_exit[far]:.1f} m from the apartment door", "Evacuation distance above the configured limit.", [far], at=rooms[far]["centroid"], unit=lab)
        # narrow doors on essential routes (to bath/wc/kitchen)
        essential = set()
        for rid, p in path_to.items():
            if rooms[rid]["type"] in ("bath", "wc", "kitchen"):
                essential |= {H[p[i]][p[i + 1]]["door"] for i in range(len(p) - 1) if H[p[i]][p[i + 1]]["door"] is not None}
        narrow = [i for i in essential if plan["doors"][i]["width"] < P["min_leaf_w"]]
        if narrow:
            add("NARROW_DOORS_ESSENTIAL", "low", f"{len(narrow)} of {len(essential)} doors on routes to kitchen and bathrooms are narrower than {P['min_leaf_w']:.2f} m",
                "Wheelchair and stroller users may not pass (leaf width; clear opening is smaller).", doors_=sorted(narrow), at=plan["doors"][sorted(narrow)[0]]["mid"], unit=lab)
        # ground-floor intrusion scenario (informational)
        entry = []
        if P["ground_floor_scenario"]:
            for r in ur:
                if r.get("windows") and r["type"] in ("kitchen", "bath", "wc", "corridor"):
                    # can an intruder from this room reach the apartment door without crossing a bedroom?
                    H2 = H.subgraph([x for x in H.nodes if rooms[x]["type"] != "room"]).copy()
                    if r["id"] in H2 and e_room in H2 and nx.has_path(H2, r["id"], e_room):
                        entry.append(r["id"])
            if entry:
                add("WINDOW_ROUTE_BYPASSES_BEDROOMS", "scenario", f"If this were a ground floor: windows of {', '.join(entry)} lead to the front door without crossing a bedroom",
                    "Intruder (or night-time wanderer) could move through the apartment without passing any bedroom door. Informational: this floor plan is an upper floor.", entry, at=rooms[entry[0]]["centroid"], unit=lab)
        # ------- Monte Carlo personas -------
        kitchens = [r["id"] for r in ur if r["type"] == "kitchen"]
        beds = [r["id"] for r in ur if r["type"] == "room"]
        wets = [r["id"] for r in ur if r["type"] in ("bath", "wc")]
        stats = dict(arrival=Counter(), night=Counter(), guest=Counter(), fail_by_mob=Counter(), n_by_mob=Counter())
        room_traffic = Counter(); door_traffic = Counter()
        def walk(p):
            for x in p: room_traffic[x] += 1
            for i in range(len(p) - 1):
                d = H[p[i]][p[i + 1]]["door"]
                if d is not None: door_traffic[d] += 1
        mobs, w = zip(*P["mobility_mix"].items())
        for _ in range(P["n_personas"]):
            mob = rng.choices(mobs, w)[0]; need = P["mobility_need"][mob]
            # 1) arrival with shopping -> kitchen
            if kitchens:
                k = rng.choice(kitchens); p = path_to.get(k)
                if p:
                    walk(p); stats["arrival"]["n"] += 1; stats["n_by_mob"][mob] += 1
                    ws = [H[p[i]][p[i + 1]]["width"] for i in range(len(p) - 1)] + [e_door["width"]]
                    if min(ws) < need: stats["arrival"]["blocked"] += 1; stats["fail_by_mob"][mob] += 1
            # 2) night trip bedroom -> nearest wet room
            if beds and wets:
                b = rng.choice(beds)
                best = min(((nx.shortest_path_length(H, b, w_, weight="weight"), w_) for w_ in wets if nx.has_path(H, b, w_)), default=None)
                if best:
                    p = nx.shortest_path(H, b, best[1], weight="weight"); walk(p); stats["night"]["n"] += 1
                    crossed = [x for x in p[1:-1] if rooms[x]["type"] == "room"]
                    if crossed: stats["night"]["crosses_other_bedroom"] += 1
                    stats["night"]["len_sum"] += best[0]
            # 3) guest -> bathroom
            if wets:
                g = rng.choice(wets); p = path_to.get(g)
                if p:
                    walk(p); stats["guest"]["n"] += 1
                    if any(rooms[x]["type"] == "room" for x in p[:-1]): stats["guest"]["crosses_bedroom"] += 1
        rate = lambda a, b: round(100 * stats[a][b] / max(1, stats[a]["n"]), 1)
        per_unit[lab] = dict(entrance_room=e_room, entrance_door=e_door["idx"], rooms=[r["id"] for r in ur],
            arrival_blocked_pct=rate("arrival", "blocked"),
            night_cross_bedroom_pct=rate("night", "crosses_other_bedroom"),
            night_avg_len_m=round(stats["night"]["len_sum"] / max(1, stats["night"]["n"]), 1),
            guest_cross_bedroom_pct=rate("guest", "crosses_bedroom"),
            blocked_by_mobility={m: round(100 * stats["fail_by_mob"][m] / max(1, stats["n_by_mob"][m]), 1) for m in P["mobility_mix"]},
            room_traffic=dict(room_traffic), door_traffic={int(k): v for k, v in door_traffic.items()}, max_exit_m=round(dist_exit[far], 1) if far else None)
    # order findings: high, medium, low, data, scenario
    order = {"high": 0, "medium": 1, "low": 2, "data": 3, "scenario": 4}
    findings.sort(key=lambda f: order[f["severity"]])
    for i, f in enumerate(findings, 1): f["n"] = i
    return plan, G, findings, per_unit, P, uniq
