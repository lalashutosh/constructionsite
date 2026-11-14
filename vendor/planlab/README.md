# planlab: quick floor-plan review prototype

Reads a DXF floor plan (Swiss Dwellings style layers: ROOM_OUTLINE, DOOR, WINDOW, WALL, UNIT_OUTLINE, ROOM_TEXT),
builds a room/door graph, runs deterministic checks, samples thousands of simple occupant trips (no LLM, milliseconds),
and draws every finding on the plan.

    pip install ezdxf shapely networkx matplotlib
    python3 render.py plan.dxf out.png      # writes out.png and out.json

Files: planlab.py (parse + graph), analysis.py (rules + sampled occupants), render.py (overlay image + JSON).
Thresholds and the mobility mix are in analysis.DEFAULTS and are assumptions, not code requirements.
Plans: Swiss Dwellings v3.0.0 (Archilyse AG), CC BY 4.0, as rendered in the Junction dataset.
