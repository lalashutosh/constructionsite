"""Decision ledger: rank candidate decisions by their impact on a quantity, and
filter options by physical fit. Two lanes:
  - `vibe`: pick a preset -> every decision is left at its default, tag `defaulted`.
  - `decide`: the user answers the top-impact questions -> tag `chosen`.

Impact of a decision d = max_option Q(o) - min_option Q(o), over options that
physically fit, in the quantity's own unit. The top 3 by impact are flagged as
open questions; the rest stay defaulted but are still listed (never silently
dropped).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from contracts.proof import Decision, Option, Tag

FitFn = Callable[[Any], tuple[bool, Optional[str]]]
QuantityFn = Callable[[Any], float]


def _always_fits(_value: Any) -> tuple[bool, Optional[str]]:
    return True, None


@dataclass
class DecisionSpec:
    key: str
    question: str
    options: list[tuple[Any, str]]  # (value, label)
    default: Any
    quantity_fn: QuantityFn           # option value -> total quantity if that option were chosen
    fits_fn: FitFn = field(default=_always_fits)


def door_leaf_fit(opening_width_m: float, clear_passage_min_m: float = 0.0) -> FitFn:
    """A leaf fits if leaf width <= opening width (and leaves at least the required clear passage)."""

    def fits(leaf_width_m: Any) -> tuple[bool, Optional[str]]:
        leaf_width_m = float(leaf_width_m)
        if leaf_width_m > opening_width_m:
            return False, f"opening is {opening_width_m:g} m: too narrow for a {leaf_width_m:g} m leaf"
        if clear_passage_min_m and leaf_width_m < clear_passage_min_m:
            return False, f"leaf {leaf_width_m:g} m gives less than the required {clear_passage_min_m:g} m clear passage"
        return True, None

    return fits


def rank(specs: list[DecisionSpec]) -> list[Decision]:
    decisions: list[Decision] = []
    for spec in specs:
        fit_totals: list[float] = []
        options: list[Option] = []
        for value, label in spec.options:
            fits, reason = spec.fits_fn(value)
            total = spec.quantity_fn(value) if fits else None
            if total is not None:
                fit_totals.append(total)
            options.append(Option(value=value, label=label, fits=fits, note=reason))

        default_total = spec.quantity_fn(spec.default)
        for opt in options:
            if opt.fits:
                opt.total_delta = round(spec.quantity_fn(opt.value) - default_total, 6)

        impact = (max(fit_totals) - min(fit_totals)) if len(fit_totals) >= 2 else 0.0
        decisions.append(
            Decision(key=spec.key, question=spec.question, options=options, default=spec.default,
                      tag=Tag.open, impact=round(impact, 6))
        )

    decisions.sort(key=lambda d: d.impact, reverse=True)
    for i, d in enumerate(decisions):
        d.tag = Tag.open if i < 3 else Tag.defaulted
    return decisions
