import json

import cv2
import numpy as np

from engine import scancheck


class FakeReviewer:
    def __init__(self, reply, kind):
        self.reply, self.kind = reply, kind

    def complete_vision(self, system, user, png, max_tokens=700):
        class R:
            pass
        r = R()
        r.text, r.usd = json.dumps(self.reply), 0.001
        return r


def _sheet():
    img = np.full((400, 900, 3), 255, np.uint8)
    cv2.rectangle(img, (40, 40), (360, 360), (0, 0, 0), 6)        # view 1
    cv2.rectangle(img, (520, 40), (860, 360), (0, 0, 0), 6)       # view 2
    return img


def _walls(x0, x1):
    return [{"outer": [[x0, 40], [x1, 40], [x1, 46], [x0, 46]], "holes": []}]


def test_reviewers_decide_view_types_and_flags_need_consensus():
    img = _sheet()
    vs = scancheck.views(img)
    assert len(vs) == 2
    site = next(v["n"] for v in vs if v["box"][0] < 400)
    plan = next(v["n"] for v in vs if v["box"][0] >= 400)
    a = {"views": [{"n": site, "type": "site_plan", "better": "A"}, {"n": plan, "type": "floor_plan", "better": "A",
                                                                       "walls_missing": True}], "text_mirrored": True}
    b = {"views": [{"n": site, "type": "site_plan", "better": "A"}, {"n": plan, "type": "floor_plan", "better": "A"}],
         "text_mirrored": False}
    out = scancheck.check(img, _walls(40, 360) + _walls(520, 860), [], None,
                          [FakeReviewer(a, "fast"), FakeReviewer(b, "strong")])
    types = {v["n"]: v["type"] for v in out["views"]}
    assert types[site] == "site_plan" and types[plan] == "floor_plan"
    assert all(w["outer"][0][0] >= 520 for w in out["walls"])          # no walls kept in the site plan
    assert not any("mirrored" in w for w in out["warnings"])          # one reviewer is not a consensus
    assert not any("missing" in w for w in out["warnings"])
    assert out["reviewer"]["models"] == ["fast", "strong"]


def test_without_reviewers_cv_rules_still_decide():
    out = scancheck.check(_sheet(), _walls(40, 360), _walls(40, 360), None, None)
    assert out["reviewer"]["used"] is False and out["walls"]


def test_one_reviewer_is_not_a_consensus():
    img = _sheet()
    vs = scancheck.views(img)
    a = {"views": [{"n": v["n"], "type": "floor_plan", "better": "A", "walls_missing": True} for v in vs],
         "text_mirrored": True}
    out = scancheck.check(img, _walls(40, 360), [], None, [FakeReviewer(a, "fast")])
    assert not any("mirrored" in w or "missing" in w for w in out["warnings"])
