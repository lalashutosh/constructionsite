"""LLM planner: question + schema + what is in THIS drawing -> validated query_spec. The LLM never returns the number;
code executes the spec. Multi-part questions = several specs combined in code (`combine`)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional

from contracts.proof import Cost, SheetFacts
from engine.query import rules as R
from engine.query.llm import LLM
from engine.query.run import SCHEMA, SpecError, validate

SYSTEM = (
    "You translate a question about ONE architectural drawing into a JSON query spec. "
    "Reply with JSON only: either one spec object or {\"parts\": [spec, ...], \"combine\": \"sum\"|\"list\"|\"difference\"|\"ratio\"|\"greater\"|\"less\"} for multi-part "
    "questions (greater/less = is part1 more/fewer than part2: use for yes/no comparisons like 'more windows than "
    "doors?'; difference/ratio = part1 minus/over part2 for 'how many more'). "
    "For 'what share / percentage / fraction of X is Y' use two parts with combine ratio (part1 = Y, part2 = X, "
    "e.g. sum_area of bathrooms over sum_area of all rooms). "
    "Use aggregate argmax_area/argmin_area for 'which room is largest/smallest', argmax_group/argmin_group with group_by "
    "for 'which apartment/storey has the most/fewest X', avg_area for averages; for sum_attr "
    "use an attr listed under numeric_attrs for that kind (e.g. volume_m3). If the question needs something the schema "
    "cannot express (direction, facing, orientation, adjacency to the entrance, cost, time), reply "
    "{\"unsupported\": \"<short reason>\"} instead of a spec. "
    "NEVER include a numeric answer; only describe what to select. Use only the allowed keys, element kinds, room types and rules."
)


class PlannerError(ValueError):
    """The LLM was called but its reply was unusable; carries the cost so it is still accounted."""

    def __init__(self, msg: str, cost: Cost):
        super().__init__(msg)
        self.cost = cost


@dataclass
class Plan:
    specs: list[dict]
    combine: str = "single"
    cost: Cost = field(default_factory=Cost)


def drawing_vocabulary(facts: SheetFacts) -> dict:
    return {
        "element_kinds": sorted({e.kind for e in facts.elements}),
        "room_types": sorted({e.subtype for e in facts.elements if e.kind == "room" and e.subtype}),
        "storeys": sorted({str(e.attrs["storey"]) for e in facts.elements if "storey" in e.attrs}),
        # numeric attributes per kind, so sum_attr names a real one (walls: volume_m3, length_m, area_m2 ...)
        "numeric_attrs": {k: sorted({a for e in facts.elements if e.kind == k for a, v in e.attrs.items()
                                     if isinstance(v, (int, float)) and not isinstance(v, bool)})
                          for k in sorted({e.kind for e in facts.elements})},
        "rules": sorted(R.RULES),
    }


def _parse_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise SpecError("no JSON in planner reply")
    return json.loads(m.group(0))


def plan(question: str, facts: SheetFacts, llm: LLM) -> Plan:
    vocab = drawing_vocabulary(facts)
    from engine.label_reader import glossary_text
    user = (f"Question: {question}\nSchema: {json.dumps(SCHEMA)}\nThis drawing: {json.dumps(vocab)}\n"
            f"Plan abbreviations (label -> room type): {glossary_text()}")
    budget = getattr(llm, "plan_tokens", 500)        # reasoning models need room to think before the JSON
    reply = llm.complete(SYSTEM, user, max_tokens=budget)
    cost = Cost(tokens_in=reply.tokens_in, tokens_out=reply.tokens_out, usd=reply.usd, llm_calls=1, planner_calls=1)
    if not re.search(r"\{.*\}", reply.text or "", re.S):        # empty / prose reply: one stricter retry
        reply = llm.complete(SYSTEM + " Output ONLY the JSON object, starting with '{'.", user, max_tokens=budget)
        cost = Cost(tokens_in=cost.tokens_in + reply.tokens_in, tokens_out=cost.tokens_out + reply.tokens_out,
                    usd=cost.usd + reply.usd, llm_calls=2, planner_calls=1)
    try:
        obj = _parse_json(reply.text)
        if "unsupported" in obj:
            raise SpecError(f"unsupported: {str(obj['unsupported'])[:120]}")
        if "parts" in obj:
            if obj.get("combine", "sum") not in ("sum", "list", "difference", "ratio", "greater", "less"):
                raise SpecError("unknown combine")
            specs, comb = obj["parts"], obj.get("combine", "sum")
            if not isinstance(specs, list) or not specs or len(specs) > 6:
                raise SpecError("bad parts")
        else:
            specs, comb = [obj], "single"
        kinds = set(vocab["element_kinds"])
        return Plan([validate(s, known_kinds=kinds) for s in specs], comb, cost)
    except (SpecError, ValueError, KeyError, TypeError) as e:
        raise PlannerError(f"{type(e).__name__}: {e}", Cost(
            tokens_in=cost.tokens_in, tokens_out=cost.tokens_out, usd=cost.usd, llm_calls=1)) from e
