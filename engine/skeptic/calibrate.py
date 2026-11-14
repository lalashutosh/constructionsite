"""Calibrator: P(correct) from voter disagreement, TTA spread, element confidence, image width, intent, sheet type.

Trained on DEV rows only (split == "dev"); model selection by 5-fold CV grouped by path hash. Seeds fixed (7).
Registered through registry.register_calibrator; display only, it never changes a tier.
"""
from __future__ import annotations

import hashlib
import json
import pathlib

import numpy as np

SEED = 7
MODEL_PATH = pathlib.Path(__file__).resolve().parent / "models" / "calibrator.joblib"
SHEET_TYPES = ["floor_plan", "elevation", "section", "site_plan", "detail", "multi_view", "schedule", "not_a_plan", "unknown"]
FEATURES = ["n_voters", "disagreement", "tta_spread", "median_conf", "width", "intent_id", "sheet_type", "n_defaulted"]


def intent_id(name: str) -> int:
    return int(hashlib.sha1((name or "unknown").encode()).hexdigest(), 16) % 97


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def featurize(po: dict, width: float = 0.0, sheet_type: str = "unknown") -> list[float]:
    voters = [v for v in (po.get("voters") or []) if _num(v.get("value")) is not None]
    vals = [_num(v["value"]) for v in voters]
    disagree = (max(vals) - min(vals)) if len(vals) >= 2 else 0.0
    spread = 0.0
    for v in voters:
        runs = [_num(r) for r in (v.get("runs") or []) if _num(r) is not None]
        if len(runs) >= 2:
            spread = max(spread, max(runs) - min(runs))
    confs = [e.get("conf", 1.0) for e in (po.get("evidence") or [])]
    n_def = sum(1 for v in (po.get("voters") or []) if "prior" in (v.get("name") or "") or "default" in (v.get("name") or ""))
    return [float(len(voters)), float(disagree), float(spread), float(np.median(confs)) if confs else 0.0, float(width),
            float(intent_id(po.get("intent"))), float(SHEET_TYPES.index(sheet_type) if sheet_type in SHEET_TYPES else 8),
            float(n_def)]


def _width(path: str) -> float:
    try:
        from PIL import Image
        from evalkit.data import dataset_root
        return float(Image.open(dataset_root() / path).size[0])
    except Exception:  # noqa: BLE001
        return 0.0


def load_rows(run_dir: pathlib.Path):
    X, y, groups = [], [], []
    for line in (run_dir / "results.jsonl").open():
        r = json.loads(line)
        if r.get("split") != "dev" or not r.get("po") or r.get("type") != "count":
            continue
        X.append(featurize(r["po"], _width(r["path"])))
        y.append(int(bool(r.get("correct"))))
        groups.append(int(hashlib.sha1(r["path"].encode()).hexdigest(), 16) % 10**9)
    return np.array(X), np.array(y), np.array(groups)


def reliability(p: np.ndarray, y: np.ndarray, bins: int = 10):
    rows = []
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        m = (p >= lo) & ((p < hi) if b < bins - 1 else (p <= hi))
        rows.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": int(m.sum()),
                     "mean_pred": float(p[m].mean()) if m.any() else None,
                     "frac_correct": float(y[m].mean()) if m.any() else None})
    return rows


def train(run: str = "latest", out_json: pathlib.Path | None = None) -> dict:
    import joblib
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import log_loss
    from sklearn.model_selection import GroupKFold, cross_val_predict
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    run_dir = pathlib.Path("evalkit/out") / run
    X, y, g = load_rows(run_dir)
    res = {"run": str(run_dir.resolve()), "n_dev_rows": int(len(y)), "base_rate": float(y.mean()) if len(y) else None}
    if len(y) < 50 or y.min() == y.max():
        res["note"] = "not enough variation to train"
        return res
    cands = {
        "logistic": make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=500, random_state=SEED)),
        "gbm": GradientBoostingClassifier(n_estimators=80, max_depth=2, learning_rate=0.05, subsample=0.8, random_state=SEED),
    }
    cv = GroupKFold(n_splits=5)
    scores, preds = {}, {}
    for k, m in cands.items():
        p = cross_val_predict(m, X, y, groups=g, cv=cv, method="predict_proba")[:, 1]
        scores[k], preds[k] = float(log_loss(y, np.clip(p, 1e-4, 1 - 1e-4))), p
    best = min(scores, key=scores.get)
    final = cands[best].fit(X, y)
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": final, "features": FEATURES}, MODEL_PATH)
    p = preds[best]
    res.update(model=best, cv_logloss=scores, cv_brier=float(np.mean((p - y) ** 2)), reliability_cv=reliability(p, y), acc_vs_coverage_cv=accuracy_vs_coverage(p, y),
               per_tier_dev=per_tier(run_dir),
               trained_rows=int(len(y)), seed=SEED)
    (MODEL_PATH.parent / "calibrator.json").write_text(json.dumps({k: res[k] for k in ("run", "model", "n_dev_rows", "seed")}))
    if out_json:
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(res, indent=2))
    return res


def per_tier(run_dir: pathlib.Path) -> dict:
    out: dict = {}
    for line in (run_dir / "results.jsonl").open():
        r = json.loads(line)
        if r.get("split") != "dev" or r.get("type") != "count":
            continue
        t = r.get("tier") or "none"
        d = out.setdefault(t, [0, 0])
        d[0] += 1
        d[1] += int(bool(r.get("correct")))
    return {k: {"n": v[0], "accuracy": v[1] / v[0]} for k, v in out.items()}


def accuracy_vs_coverage(p: np.ndarray, y: np.ndarray, grid=(1.0, 0.8, 0.6, 0.4, 0.2)):
    order = np.argsort(-p)
    out = []
    for c in grid:
        k = max(1, int(round(c * len(y))))
        out.append({"coverage": c, "n": k, "accuracy": float(y[order[:k]].mean())})
    return out


_cache = {}


def predict(po: dict) -> float | None:
    import joblib
    if "m" not in _cache:
        if not MODEL_PATH.exists():
            _cache["m"] = None
        else:
            _cache["m"] = joblib.load(MODEL_PATH)
    m = _cache["m"]
    if m is None:
        return None
    x = np.array([featurize(po, _width((po.get("provenance") or {}).get("file", "")))])
    return float(m["model"].predict_proba(x)[0, 1])


def register() -> None:
    from engine import registry
    if MODEL_PATH.exists():
        registry.register_calibrator("skeptic_calibrator", predict)
