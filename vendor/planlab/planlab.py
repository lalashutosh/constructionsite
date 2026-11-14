"""planlab: DXF floor plan -> room/door graph -> cheap rule checks + sampled occupant paths."""
import math, re, random, json, itertools
import ezdxf, networkx as nx
from shapely.geometry import Polygon, Point, LineString
from shapely.ops import unary_union

NAME_TYPES = {  # multilingual room-name -> type
    "stanza": "room", "zimmer": "room", "chambre": "room", "wohnzimmer": "room", "camera": "room", "salotto": "room",
    "cucina": "kitchen", "küche": "kitchen", "kueche": "kitchen", "cuisine": "kitchen", "kochen": "kitchen",
    "bagno": "bath", "bad": "bath", "salle de bain": "bath", "doccia": "bath", "wc": "wc", "toilette": "wc",
    "corridoio": "corridor", "korridor": "corridor", "couloir": "corridor", "flur": "corridor", "entrata": "corridor",
    "soggiorno": "living", "soggiorno/pranzo": "living", "wohnen": "living", "wohnen/essen": "living", "séjour": "living", "salon": "living",
    "ripostiglio": "storage", "abstellraum": "storage", "réduit": "storage", "cantina": "storage",
    "balcone": "balcony", "balkon": "balcony", "loggia": "balcony", "terrasse": "balcony",
}
def rtype(name):
    n = (name or "").lower().strip()
    return NAME_TYPES.get(n, "other")

def _pts(e): return [(float(x), float(y)) for x, y in e.get_points("xy")]

def load(dxf_path):
    d = ezdxf.readfile(dxf_path); msp = d.modelspace()
    L = lambda name: [e for e in msp if e.dxf.layer == name]
    # rooms
    polys = []
    for e in L("ROOM_OUTLINE"):
        if e.dxftype() == "LWPOLYLINE" and e.closed and len(_pts(e)) >= 3:
            p = Polygon(_pts(e))
            if p.is_valid and p.area > 0.5: polys.append(p)
    texts = [(e.dxf.text, e.dxf.insert.x, e.dxf.insert.y) for e in L("ROOM_TEXT")]
    rooms = []
    for p in polys:
        inside = [t for t in texts if p.contains(Point(t[1], t[2]))]
        inside.sort(key=lambda t: -t[2])
        name = num = area = None
        for t, _, _ in inside:
            if re.fullmatch(r"\d+\.\d+", t): num = t
            elif re.search(r"m²", t): area = float(re.sub(r"[^0-9.]", "", t))
            else: name = t
        rooms.append(dict(poly=p, name=name, num=num, area_label=area, type=rtype(name), area=p.area))
    rooms = [r for r in rooms if r["num"]]          # numbered rooms only
    for r in rooms:                                  # unnamed small room -> WC / shaft (heuristic, flagged)
        if r["type"] == "other" and r["name"] is None:
            r["type"] = "wc" if r["area"] < 3.0 else "other"; r["inferred_type"] = True
    for i, r in enumerate(rooms): r["id"] = r["num"]
    units = [Polygon(_pts(e)) for e in L("UNIT_OUTLINE") if len(_pts(e)) >= 3 and Polygon(_pts(e)).area > 5]
    # doors: arcs give hinge+radius; leaf line gives open end
    leaves = [LineString(_pts(e)) for e in L("DOOR") if e.dxftype() == "LWPOLYLINE" and len(_pts(e)) == 2]
    doors = []
    for a in [e for e in L("DOOR") if e.dxftype() == "ARC"]:
        c = (a.dxf.center.x, a.dxf.center.y); r = a.dxf.radius
        s, t = math.radians(a.dxf.start_angle), math.radians(a.dxf.end_angle)
        if t < s: t += 2 * math.pi
        ends = [(c[0] + r * math.cos(s), c[1] + r * math.sin(s)), (c[0] + r * math.cos(t), c[1] + r * math.sin(t))]
        # the end touched by the leaf line is the OPEN end; the other is the closed (in-wall) end
        best = min(leaves, key=lambda l: min(l.distance(Point(ends[0])), l.distance(Point(ends[1])))) if leaves else None
        d0 = best.distance(Point(ends[0])) if best else 0; d1 = best.distance(Point(ends[1])) if best else 1
        closed = ends[1] if d0 < d1 else ends[0]
        mid = ((c[0] + closed[0]) / 2, (c[1] + closed[1]) / 2)
        # swing sector polygon
        n = 14; ang = [s + (t - s) * k / n for k in range(n + 1)]
        sector = Polygon([c] + [(c[0] + r * math.cos(x), c[1] + r * math.sin(x)) for x in ang])
        doors.append(dict(hinge=c, width=r, closed=closed, mid=mid, sector=sector))
    wins = []
    for e in L("WINDOW"):
        p = _pts(e)
        if len(p) >= 4:
            pg = Polygon(p)
            if pg.area > 0.01: wins.append(pg)
    walls = [Polygon(_pts(e)) for e in L("WALL") if e.dxftype() == "LWPOLYLINE" and len(_pts(e)) >= 3 and Polygon(_pts(e)).is_valid]
    title = next((e.dxf.text for e in L("ANNOTATION")), "")
    return dict(rooms=rooms, units=units, doors=doors, windows=wins, walls=walls, title=title)

def _room_at(rooms, pt, tol=0.02):
    P = Point(pt)
    for r in rooms:
        if r["poly"].buffer(tol).contains(P): return r
    return None

def build_graph(plan):
    rooms = plan["rooms"]; G = nx.Graph()
    for r in rooms:
        cen = r["poly"].representative_point()
        unit = next((i for i, u in enumerate(plan["units"]) if u.contains(cen)), None)
        r["unit"] = unit; r["centroid"] = (cen.x, cen.y)
        G.add_node(r["id"], **{k: r[k] for k in ("name", "type", "unit", "centroid", "area")})
    G.add_node("OUTSIDE", name="outside", type="outside", unit=None, centroid=None, area=0)
    for i, dr in enumerate(plan["doors"]):
        hx, hy = dr["hinge"]; cx, cy = dr["closed"]; dx, dy = cx - hx, cy - hy
        L = math.hypot(dx, dy) or 1; nx_, ny_ = -dy / L, dx / L
        mx, my = dr["mid"]
        def side(sg):
            for k in (0.2, 0.35, 0.55, 0.8):
                r_ = _room_at(rooms, (mx + sg * nx_ * k, my + sg * ny_ * k))
                if r_: return r_
            return None
        a, b = side(+1), side(-1)
        dr["a"], dr["b"] = (a["id"] if a else "OUTSIDE"), (b["id"] if b else "OUTSIDE")
        dr["idx"] = i
        if dr["a"] != dr["b"]:
            G.add_edge(dr["a"], dr["b"], door=i, width=dr["width"], mid=dr["mid"], kind="door")
    # open boundaries: outlines almost touch (<6 cm) along >0.8 m and no wall polygon fills the gap -> open-plan connection
    W = unary_union([w.buffer(0) for w in plan["walls"]]) if plan["walls"] else None
    for r1, r2 in itertools.combinations(rooms, 2):
        if G.has_edge(r1["id"], r2["id"]): continue
        d = r1["poly"].distance(r2["poly"])
        if d > 0.06: continue
        face = r1["poly"].boundary.intersection(r2["poly"].buffer(d + 0.05))
        if face.length < 0.8: continue
        gap = r1["poly"].buffer(d / 2 + 0.02).intersection(r2["poly"].buffer(d / 2 + 0.02))
        cover = (gap.intersection(W).area / gap.area) if (W is not None and gap.area > 0) else 0
        if cover < 0.3:
            G.add_edge(r1["id"], r2["id"], door=None, width=min(face.length, 3.0), mid=face.centroid.coords[0], kind="open")
    # windows -> rooms
    for w in (plan["windows"] if rooms else []):
        r = min(rooms, key=lambda r: r["poly"].distance(w))
        if r["poly"].distance(w) < 0.4: r.setdefault("windows", []).append(w)
    return G

def edge_len(G, u, v):
    cu, cv = G.nodes[u]["centroid"], G.nodes[v]["centroid"]
    return math.dist(cu, cv)

def travel_graph(G):
    """weighted graph: room centroid -> door -> centroid (Euclidean), OUTSIDE excluded."""
    H = nx.Graph()
    for u, v, d in G.edges(data=True):
        if "OUTSIDE" in (u, v): continue
        m = d["mid"]; cu, cv = G.nodes[u]["centroid"], G.nodes[v]["centroid"]
        H.add_edge(u, v, weight=math.dist(cu, m) + math.dist(m, cv), door=d["door"], width=d["width"])
    return H
