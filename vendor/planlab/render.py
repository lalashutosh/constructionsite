import sys, math, json
sys.path.insert(0, "/home/claude/planlab")
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MPoly, Wedge, Circle
import textwrap
import analysis as A

TYPE_COL = {"room": "#eef3fb", "living": "#e8f4ea", "kitchen": "#fdf1de", "bath": "#e3f1f7", "wc": "#e3f1f7",
            "corridor": "#f4f4f4", "balcony": "#eaf2e0", "storage": "#f0ece4", "other": "#f4f4f4"}
SEV_COL = {"high": "#d62728", "medium": "#e8890c", "low": "#c9a400", "data": "#7f4fb8", "scenario": "#2a7fbf"}

def render(dxf, out_png, title_note=""):
    plan, G, F, U, P, uniq = A.analyze(dxf)
    rooms = {r["id"]: r for r in plan["rooms"]}
    fig = plt.figure(figsize=(17, 9.5), dpi=110)
    ax = fig.add_axes([0.01, 0.02, 0.60, 0.92]); ax.set_aspect("equal"); ax.axis("off")
    for w in plan["walls"]:
        ax.add_patch(MPoly(list(w.exterior.coords), closed=True, fc="#9a9a9a", ec="#555", lw=0.4, zorder=2))
    for r in plan["rooms"]:
        ax.add_patch(MPoly(list(r["poly"].exterior.coords), closed=True, fc=TYPE_COL.get(r["type"], "#f4f4f4"), ec="none", zorder=1))
        cx, cy = r["centroid"]
        ax.text(cx, cy, f"{r['num']}\n{r['name'] or r['type']}", ha="center", va="center", fontsize=6.3, color="#333", zorder=6)
    for w in plan["windows"]:
        ax.add_patch(MPoly(list(w.exterior.coords), closed=True, fc="#8fc3ee", ec="#3b79b0", lw=0.5, zorder=3))
    flagged_doors = {d for f in F for d in f["doors"]}
    dup_ids = {f2 for f in F if f["rule"] == "DUPLICATE_DOOR_ENTITIES" for f2 in f["doors"]}
    for d in plan["doors"]:
        hx, hy = d["hinge"]; r = d["width"]
        xs, ys = d["sector"].exterior.xy
        ax.add_patch(MPoly(list(zip(xs, ys)), closed=True, fc="none", ec="#444", lw=0.6, ls=":", zorder=4))
        ax.plot([hx, d["closed"][0]], [hy, d["closed"][1]], color="#222", lw=1.4, zorder=5)
    # traffic heat on doors (all units)
    traffic = {}
    for lab, u in P_units(U):
        for k, v in u["door_traffic"].items(): traffic[k] = traffic.get(k, 0) + v
    mx = max(traffic.values()) if traffic else 1
    for k, v in traffic.items():
        d = plan["doors"][k]
        ax.add_patch(Circle(d["mid"], 0.12 + 0.30 * v / mx, fc="#ff7f0e", ec="none", alpha=0.35, zorder=7))
    # findings markers
    for f in F:
        col = SEV_COL[f["severity"]]
        pts = []
        for rid in f["rooms"]:
            if rid in rooms and f["severity"] in ("high", "medium"):
                ax.add_patch(MPoly(list(rooms[rid]["poly"].exterior.coords), closed=True, fc=col, alpha=0.16, ec=col, lw=1.6, zorder=8))
        for di in f["doors"]:
            if f["rule"] != "DUPLICATE_DOOR_ENTITIES" or True:
                ax.add_patch(Circle(plan["doors"][di]["mid"], 0.33, fc="none", ec=col, lw=2.0, zorder=9))
        at = f["at"]
        if f["rooms"] and f["rooms"][0] in rooms and f["severity"] in ("high", "medium", "scenario"):
            bx = rooms[f["rooms"][0]]["poly"].bounds; at = (bx[0] + 0.45, bx[3] - 0.45)
        if at:
            ax.text(at[0], at[1], str(f["n"]), color="white", fontsize=8, fontweight="bold", ha="center", va="center", zorder=11,
                    bbox=dict(boxstyle="circle,pad=0.25", fc=col, ec="white", lw=0.8))
    b = unary_bounds(plan); ax.set_xlim(b[0] - 0.5, b[2] + 0.5); ax.set_ylim(b[1] - 0.5, b[3] + 0.5)
    ax.set_title(f"{plan['title']}   ·   {len(plan['rooms'])} rooms, {len(uniq)} distinct doors ({len(plan['doors'])} symbols), {len(plan['windows'])} windows   {title_note}", fontsize=9, loc="left")
    # side panel
    tx = fig.add_axes([0.62, 0.02, 0.37, 0.92]); tx.axis("off")
    y = 0.99
    tx.text(0, y, "Plan review: findings (numbers match markers on the plan)", fontsize=10.5, fontweight="bold", va="top"); y -= 0.045
    for f in F:
        col = SEV_COL[f["severity"]]
        head = f"{f['n']}  [{f['severity'].upper()}]" + (f"  unit {f['unit']}" if f.get("unit") else "")
        tx.text(0, y, head, fontsize=8, color=col, fontweight="bold", va="top"); y -= 0.027
        for ln in textwrap.wrap(f["title"], 78)[:3]:
            tx.text(0.01, y, ln, fontsize=8, va="top"); y -= 0.024
        y -= 0.012
    y -= 0.01
    tx.text(0, y, f"Sampled occupants: {P['n_personas']} per apartment, fixed seed {P['seed']}", fontsize=9, fontweight="bold", va="top"); y -= 0.035
    for lab, u in P_units(U):
        tx.text(0, y, f"Apartment {lab}: night trip crosses another bedroom {u['night_cross_bedroom_pct']}%  ·  guest crosses a bedroom {u['guest_cross_bedroom_pct']}%  ·  furthest room to front door {u['max_exit_m']} m", fontsize=7.6, va="top", wrap=True); y -= 0.05
    tx.text(0, y, "Orange discs on doors = share of simulated trips using that door.\nAssumptions (door-width limits, mobility mix) are editable parameters.", fontsize=7.4, color="#555", va="top")
    fig.savefig(out_png, facecolor="white"); plt.close(fig)
    return plan, F, U, P

def P_units(U): return list(U.items())
def unary_bounds(plan):
    xs0 = min(r["poly"].bounds[0] for r in plan["rooms"]); ys0 = min(r["poly"].bounds[1] for r in plan["rooms"])
    xs1 = max(r["poly"].bounds[2] for r in plan["rooms"]); ys1 = max(r["poly"].bounds[3] for r in plan["rooms"])
    return xs0, ys0, xs1, ys1

if __name__ == "__main__":
    plan, F, U, P = render(sys.argv[1], sys.argv[2])
    json.dump(dict(findings=F, units={k: {x: v[x] for x in v if x not in ("room_traffic", "door_traffic")} for k, v in U.items()}, params=P), open(sys.argv[2].replace(".png", ".json"), "w"), indent=1, default=str)
    print("ok", len(F), "findings")
