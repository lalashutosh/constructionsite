"""Pretrained CubiCasa5k multi-task model (ROUTE A). CPU-only inference, no network calls.

Weights: weights/model_best_val_loss_var.pkl (CubiCasa5k authors, CC BY-NC-SA 4.0).
Architecture code vendored (not shipped/committed) at weights/_src/CubiCasa5k-master/floortrans
(see docs/decisions/weights.md for provenance and the leakage check).

Output head layout (44 channels), per the authors' eval.py:
  [0:21]  junction/corner heatmaps (unused here -- vectorisation only)
  [21:33] 12 room classes (softmax)
  [33:44] 11 icon classes (softmax)
"""
from __future__ import annotations

import os
import pathlib
import sys
import threading

import numpy as np

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "weights" / "_src" / "CubiCasa5k-master"
_WEIGHTS = _REPO_ROOT / "weights" / "model_best_val_loss_var.pkl"

ROOM_CLASSES = [
    "background", "outdoor", "wall", "kitchen", "living_room", "bedroom",
    "bath", "hallway", "railing", "storage", "garage", "other_rooms",
]
ICON_CLASSES = [
    "empty", "window", "door", "closet", "electr_appl", "toilet", "sink",
    "sauna_bench", "fire_place", "bathtub", "chimney",
]

_model = None
_lock = threading.Lock()
_available: bool | None = None


def available() -> bool:
    global _available
    if _available is None:
        _available = _SRC.exists() and _WEIGHTS.exists()
    return _available


def get_model():
    global _model
    if _model is not None:
        return _model
    with _lock:
        if _model is not None:
            return _model
        if not available():
            raise RuntimeError("CubiCasa weights/source not found under weights/; ROUTE A unavailable")
        if str(_SRC) not in sys.path:
            sys.path.insert(0, str(_SRC))
        import torch
        from floortrans.models import get_model as _get_model  # vendored, see docs/decisions/weights.md

        cwd = os.getcwd()
        os.chdir(_SRC)  # the authors' init_weights() loads a relative imagenet-style checkpoint
        try:
            m = _get_model("hg_furukawa_original", 51)
            n_classes = 44
            m.conv4_ = torch.nn.Conv2d(256, n_classes, bias=True, kernel_size=1)
            m.upsample = torch.nn.ConvTranspose2d(n_classes, n_classes, kernel_size=4, stride=4)
            ckpt = torch.load(str(_WEIGHTS), map_location="cpu")
            m.load_state_dict(ckpt["model_state"])
            m.eval()
        finally:
            os.chdir(cwd)
        _model = m
    return _model


def infer(img_rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """img_rgb: HxWx3 uint8. Returns (room_probs[12,H,W], icon_probs[11,H,W]) float32 softmax,
    resized back to the exact input H,W (the hourglass net's internal /4 ... x4 path can be off
    by a couple of px from the input size)."""
    import torch
    import torch.nn.functional as F

    # Default torch CPU thread count is low on some builds; use all cores -- this alone roughly
    # halves wall-clock inference time (measured: ~2.9s -> ~1.3-1.9s at 1 thread-pool-set per
    # process, see docs/decisions/weights.md).
    cpu_count = os.cpu_count() or 4
    if torch.get_num_threads() < cpu_count:
        torch.set_num_threads(cpu_count)

    m = get_model()
    h, w = img_rgb.shape[:2]
    x = img_rgb.astype(np.float32) / 255.0 * 2 - 1
    x = torch.from_numpy(x.transpose(2, 0, 1)).unsqueeze(0)
    with torch.no_grad():
        out = m(x)
        if out.shape[-2:] != (h, w):
            out = F.interpolate(out, size=(h, w), mode="bilinear", align_corners=False)
        rooms = F.softmax(out[0, 21:33], dim=0).numpy()
        icons = F.softmax(out[0, 33:44], dim=0).numpy()
    return rooms.astype(np.float32), icons.astype(np.float32)
