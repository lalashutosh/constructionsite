"""Hand labels (by eye, from contact sheets) for the non-cubicasa image folders, used ONLY for triage evaluation.

Key = (folder, index into the sorted list of image files in data/<folder>). Only images whose type was clear
to the labeller are listed; ambiguous ones are left out. Classes: F floor_plan, E elevation, S section,
P site_plan, D detail, M multi_view, X not_a_plan (photo, text page, manuscript, render).
"""
from __future__ import annotations

NAMES = {"F": "floor_plan", "E": "elevation", "S": "section", "P": "site_plan", "D": "detail", "M": "multi_view",
         "X": "not_a_plan"}

_RAW = {
    "europeana": "0M 1X 2F 3F 4E 5F 6F 7M 8E 9X 10F 11F 12E 13F 14X 15S 16D 17X 18D 19X 20F 22F 23E 24F 26E 27E 28E "
                 "30M 31X 32E 34M 35E",
    "wikimedia": "0F 1F 2F 3E 4P 5F 6P 7E 8F 9M 10P 11M 13F 14F 15F 16P 17F 19M 20P 21P 22F 23F 24M 25X 26E 27F 28X "
                 "29X 30F 31F 32F 33F 34F 35P 37S 39F 40P 42F 43F 44M 45M 46F 47F",
    "finna": "0F 2F 3P 6D 8E 9P 10F 11X 13E 14F 17M 18E 20S 23S 24M 25P 26S 28S 30E 31P 32S 34M 35F",
    "habs": "0P 1M 2M 3M 5P 6E 7E 8E 9E 10E 11D 13P 15M 16D 17F 20S 21M 24D 25D 26E 27M 28M",
}


def labels() -> list[tuple[str, int, str]]:
    out = []
    for folder, s in _RAW.items():
        for tok in s.split():
            out.append((folder, int(tok[:-1]), NAMES[tok[-1]]))
    return out
