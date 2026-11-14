"""Proof Object contract: the ONLY interface between agents, API and UI.

FROZEN after Wave 0. Do not edit in a worktree. If you need a change, write
contracts/CHANGE_REQUEST_<agent>.md describing field, reason and default, and keep working with `extras`/`attrs`.

Design rules baked in here:
  * Every number carries a provenance Tag (drawn / specified / chosen / defaulted / open).
  * Evidence is geometry in ORIGINAL file coordinates (image pixels, or PDF user units for vector pages).
  * Tier is computed from independent voters, never from a model's self-reported confidence.
  * Counts do not need scale. Areas, lengths, volumes do.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field

Point = tuple[float, float]
Scalar = Union[int, float, str]


class Tier(str, Enum):
    green = "green"  # >= 2 independent voters agree
    amber = "amber"  # voters disagree or confidence low: a human should look first
    grey = "grey"    # cannot answer from this input; `refusal` says why


class Tag(str, Enum):
    drawn = "drawn"          # geometry on the sheet fixes it
    specified = "specified"  # a schedule / spec / printed label on the sheet says so
    chosen = "chosen"        # a human picked it
    defaulted = "defaulted"  # standard practice under the selected vibe preset
    open = "open"            # needs a decision


class Element(BaseModel):
    id: str
    kind: str                       # door|window|room|fixture|wall|symbol|label|scale_anchor|...
    subtype: Optional[str] = None   # e.g. bedroom, wc, sink, bathtub, sauna_bench
    polygon: list[Point]            # ORIGINAL coordinates, closed or open ring
    label: Optional[str] = None     # raw OCR / CAD text if any
    conf: float = Field(1.0, ge=0.0, le=1.0)
    attrs: dict[str, Any] = Field(default_factory=dict)  # width_px, width_m, swing, area_px, ...


class Voter(BaseModel):
    name: str                        # "detector", "arc_geometry", "ocr_labels", "dxf_exact", ...
    value: Optional[Scalar] = None
    element_ids: list[str] = Field(default_factory=list)
    runs: list[Union[int, float]] = Field(default_factory=list)  # per-TTA-run values (spread = uncertainty)
    note: Optional[str] = None


class ScaleAnchor(BaseModel):
    kind: Literal["scale_bar", "dimension", "printed_ratio", "printed_area", "door_prior", "user"]
    px_per_m: float
    rel_sigma: float                 # 1-sigma relative error of this anchor
    tag: Tag
    note: Optional[str] = None
    element_ids: list[str] = Field(default_factory=list)


class ScaleInfo(BaseModel):
    px_per_m: Optional[float] = None
    rel_sigma: Optional[float] = None
    anchors: list[ScaleAnchor] = Field(default_factory=list)
    widths_relative: bool = False    # True when ONLY door_prior anchors exist: never report door widths as measured
    needs_user: bool = False         # True when the UI should ask the user (cheapest question first)


class Assumption(BaseModel):
    key: str
    value: Scalar
    unit: Optional[str] = None
    tag: Tag
    source: str                      # "vibe:standard", "user", "printed label", "code table v1", ...
    depends_on: list[str] = Field(default_factory=list)  # other assumption keys: prevents circular evidence


class Option(BaseModel):
    value: Scalar
    label: str
    total_delta: Optional[float] = None  # change of the answer if chosen, relative to default
    fits: bool = True                    # physically fits / allowed by rule pack
    note: Optional[str] = None


class Decision(BaseModel):
    key: str
    question: str
    options: list[Option]
    default: Scalar
    tag: Tag = Tag.open
    impact: float = 0.0              # spread of the answer across options, in answer units
    decide_by: Optional[str] = None  # ISO date or free text; lead times are assumptions, label them
    affects: list[str] = Field(default_factory=list)  # proof ids / element ids


class Interval(BaseModel):
    lo: float
    hi: float


class Provenance(BaseModel):
    file: str                        # path as in questions.jsonl
    sha256: Optional[str] = None
    page: Optional[int] = None
    revision: Optional[str] = None
    resolved_from: Optional[str] = None  # sibling format actually used: "dxf" | "svg" | "ifc" | "pdf" | "png"
    fmt: Optional[str] = None
    license: Optional[str] = None
    credit: Optional[str] = None     # MUST be shown whenever the drawing is shown


class Cost(BaseModel):
    ms: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    usd: float = 0.0
    llm_calls: int = 0
    planner_calls: int = 0           # LLM planner calls (no template matched); subset of llm_calls


class ProofObject(BaseModel):
    id: str
    question: str
    intent: Optional[str] = None
    kind: Literal["count", "area", "length", "volume", "text", "other"] = "count"
    value: Optional[Scalar] = None
    unit: Optional[str] = None
    interval: Optional[Interval] = None
    tier: Tier = Tier.amber
    evidence: list[Element] = Field(default_factory=list)
    voters: list[Voter] = Field(default_factory=list)
    scale: Optional[ScaleInfo] = None
    assumptions: list[Assumption] = Field(default_factory=list)
    decisions_open: list[Decision] = Field(default_factory=list)
    provenance: Provenance
    cost: Cost = Field(default_factory=Cost)
    notes: list[str] = Field(default_factory=list)
    query_spec: Optional[dict[str, Any]] = None  # set when the LLM planner built the query: exactly what code computed
    refusal: Optional[str] = None
    reliability: Optional[float] = None          # P(correct) from a calibrator trained on DEV answers (never the model's own confidence)
    reliability_note: Optional[str] = None       # where that number comes from, in words
    answer_text: Optional[str] = None            # one plain sentence built by code from `value` (no LLM)


class SheetFacts(BaseModel):
    """What an extractor knows about ONE sheet. Questions are answered from this, never from pixels again."""

    provenance: Provenance
    sheet_type: Literal[
        "floor_plan", "elevation", "section", "site_plan", "detail",
        "multi_view", "schedule", "not_a_plan", "unknown",
    ] = "unknown"
    legible: bool = True
    legibility_note: Optional[str] = None
    width_px: Optional[int] = None
    height_px: Optional[int] = None
    language: Optional[str] = None
    elements: list[Element] = Field(default_factory=list)
    scale: Optional[ScaleInfo] = None
    printed_areas: list[dict[str, Any]] = Field(default_factory=list)  # {"text","value_m2","polygon"}
    extras: dict[str, Any] = Field(default_factory=dict)
