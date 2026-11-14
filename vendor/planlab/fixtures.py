import collections
import ezdxf
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union

def clusters(dxf_path):
    msp = ezdxf.readfile(dxf_path).modelspace()
    items = []
    for e in msp:
        if e.dxf.layer != "FIXTURE": continue
        if e.dxftype() == "CIRCLE": items.append(("C", Point(e.dxf.center.x, e.dxf.center.y).buffer(e.dxf.radius)))
        elif e.dxftype() == "LWPOLYLINE":
            pts = [(float(x), float(y)) for x, y in e.get_points("xy")]
            if len(pts) >= 3 and Polygon(pts).is_valid: items.append(("P", Polygon(pts)))
    n = len(items); parent = list(range(n))
    def f(i):
        while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
        return i
    for i in range(n):
        for j in range(i + 1, n):
            if items[i][1].buffer(0.02).intersects(items[j][1]): parent[f(i)] = f(j)
    cl = collections.defaultdict(list)
    for i in range(n): cl[f(i)].append(i)
    out = []
    for v in cl.values():
        u = unary_union([items[i][1] for i in v]); b = u.bounds
        L, S = max(b[2] - b[0], b[3] - b[1]), min(b[2] - b[0], b[3] - b[1])
        out.append(dict(nC=sum(items[i][0] == "C" for i in v), nP=sum(items[i][0] == "P" for i in v), L=L, S=S, c=u.centroid.coords[0]))
    return out
