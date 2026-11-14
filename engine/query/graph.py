"""Room graph (networkx): apartments = connected groups of rooms once entrance-door edges are removed."""
from __future__ import annotations

from contracts.proof import SheetFacts

_COMMON = {"corridor", "stairs", "stair", "staircase", "elevator", "lift", "hall", "shaft", "common", "lobby"}


def room_graph(facts: SheetFacts, tol: float = 3.0):
    import networkx as nx
    from engine.query.run import _poly

    g = nx.Graph()
    rooms = [(e, _poly(e)) for e in facts.elements if e.kind == "room"]
    rooms = [(e, p) for e, p in rooms if p is not None]
    for e, _ in rooms:
        g.add_node(e.id, subtype=(e.subtype or "").lower())
    doors = [(d, _poly(d)) for d in facts.elements if d.kind == "door"]
    for i in range(len(rooms)):
        for j in range(i + 1, len(rooms)):
            (a, pa), (b, pb) = rooms[i], rooms[j]
            if pa.distance(pb) > tol:
                continue
            ent = False
            for d, pd in doors:
                if pd is not None and pd.distance(pa) <= tol and pd.distance(pb) <= tol and \
                        (d.attrs.get("entrance") or (d.subtype or "") == "entrance"):
                    ent = True
                    break
            if not ent:
                g.add_edge(a.id, b.id)
    return g


def apartment_of(facts: SheetFacts) -> dict[str, str]:
    """element id -> apartment label (A, B, ...) for rooms in dwelling components. Explicit attrs.apartment wins."""
    explicit = {e.id: str(e.attrs["apartment"]) for e in facts.elements if e.attrs.get("apartment")}
    if explicit:
        return explicit
    g = room_graph(facts)
    import networkx as nx
    out: dict[str, str] = {}
    n = 0
    for comp in sorted(nx.connected_components(g), key=lambda c: sorted(c)[0]):
        if all(g.nodes[i]["subtype"] in _COMMON for i in comp):
            continue
        label = chr(ord("A") + n % 26)
        n += 1
        for i in comp:
            out[i] = label
    return out


def count_apartments(facts: SheetFacts) -> int:
    return len(set(apartment_of(facts).values()))
