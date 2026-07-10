"""Label Studio ML backend — AgriVision YOLO pre-annotations.

Start:
  python tools/label_studio/ml_server.py

Then in Label Studio project settings → Model:
  Backend URL: http://localhost:9090
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import cv2
import numpy as np
import requests
from flask import Flask, jsonify, request

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.detection import run_detection

LOG = logging.getLogger("agrivision.label_studio")
MODEL_VERSION = "agrivision-yolo-v1"
FROM_NAME = os.environ.get("AGRIVISION_LS_FROM_NAME", "label")
TO_NAME = os.environ.get("AGRIVISION_LS_TO_NAME", "image")
MIN_CONF = float(os.environ.get("AGRIVISION_LS_MIN_CONF", "0.35"))

app = Flask(__name__)


def _auth_headers() -> dict[str, str]:
    token = os.environ.get("LABEL_STUDIO_API_KEY", "").strip()
    if not token:
        return {}
    return {"Authorization": f"Token {token}"}


def _resolve_image_url(task: dict) -> str | None:
    data = task.get("data") or {}
    ref = data.get("image") or data.get("image_url")
    if not ref:
        return None
    ref = str(ref)
    if ref.startswith("http://") or ref.startswith("https://"):
        return ref
    base = os.environ.get("LABEL_STUDIO_URL", "http://localhost:8080").rstrip("/")
    if ref.startswith("/"):
        return f"{base}{ref}"
    return ref


def _load_image(task: dict) -> np.ndarray | None:
    ref = _resolve_image_url(task)
    if not ref:
        return None

    path = Path(ref)
    if path.is_file():
        img = cv2.imread(str(path))
        return img

    try:
        resp = requests.get(ref, headers=_auth_headers(), timeout=60)
        resp.raise_for_status()
    except Exception as exc:
        LOG.warning("Failed to fetch image %s: %s", ref, exc)
        return None

    arr = np.frombuffer(resp.content, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def _class_label(det: dict) -> str:
    raw = str(det.get("label", ""))
    if "(" in raw:
        raw = raw.split("(", 1)[0].strip()
    if raw:
        return raw
    cls = det.get("class")
    return f"class_{cls}" if cls is not None else "unknown"


def _det_to_ls_result(det: dict, w: int, h: int) -> dict:
    x1, y1, x2, y2 = det["bbox"]
    conf = float(det.get("confidence", 0.0))
    return {
        "from_name": FROM_NAME,
        "to_name": TO_NAME,
        "type": "rectanglelabels",
        "value": {
            "x": max(0.0, x1 / w * 100.0),
            "y": max(0.0, y1 / h * 100.0),
            "width": max(0.0, (x2 - x1) / w * 100.0),
            "height": max(0.0, (y2 - y1) / h * 100.0),
            "rotation": 0,
            "rectanglelabels": [_class_label(det)],
        },
        "score": conf,
    }


def _predict_task(task: dict) -> dict:
    frame = _load_image(task)
    if frame is None:
        return {"result": [], "score": 0.0, "model_version": MODEL_VERSION}

    h, w = frame.shape[:2]
    dets = run_detection(frame)
    results = [_det_to_ls_result(d, w, h) for d in dets if d.get("confidence", 0) >= MIN_CONF]
    score = max((r["score"] for r in results), default=0.0)
    return {"result": results, "score": score, "model_version": MODEL_VERSION}


@app.route("/health", methods=["GET"])
@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "UP", "model": MODEL_VERSION})


@app.route("/setup", methods=["POST"])
def setup():
    return jsonify({"model_version": MODEL_VERSION})


@app.route("/predict", methods=["POST"])
def predict():
    body = request.get_json(silent=True) or {}
    tasks = body.get("tasks") or []
    out = []
    for task in tasks:
        out.append(_predict_task(task))
    return jsonify({"results": out})


@app.route("/validate", methods=["POST"])
def validate():
    return jsonify({"status": "ok"})


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    host = os.environ.get("AGRIVISION_ML_HOST", "0.0.0.0")
    port = int(os.environ.get("AGRIVISION_ML_PORT", "9090"))
    LOG.info("AgriVision YOLO ML backend on http://%s:%s", host, port)
    LOG.info("Connect in Label Studio → Settings → Model → http://localhost:%s", port)
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
