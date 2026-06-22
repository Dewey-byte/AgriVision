"""Export Label Studio annotations to AgriVision YOLO layout.

Label Studio's built-in "YOLO with Images" export fails on Windows when images
were imported via Local Files (URLs like /data/local-files/?d=banana%5CDJI_0100).

Workaround:
  1. In Label Studio: Export -> JSON (not YOLO)
  2. Run this script:

     python tools/label_studio/export_yolo.py ^
       --json path/to/export.json ^
       --local-files-root "C:/path/to/your/image/folder" ^
       --output datasets/yolo_banana

Or fetch directly from a running Label Studio project:

     python tools/label_studio/export_yolo.py ^
       --project-id 1 ^
       --url http://localhost:8080 ^
       --api-key YOUR_LEGACY_TOKEN ^
       --local-files-root datasets/inbox ^
       --output datasets/yolo_banana
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import requests

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CLASS_NAMES = ["black_sigatoka", "healthy", "moko", "panama"]
CLASS_TO_ID = {name: idx for idx, name in enumerate(CLASS_NAMES)}
WIN_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _safe_stem(name: str) -> str:
    stem = Path(name.replace("\\", "/")).stem
    stem = WIN_INVALID.sub("_", stem).strip().strip(".")
    return stem or "image"


def _image_ref_from_task(task: dict) -> str:
    data = task.get("data") or {}
    return str(data.get("image") or data.get("image_url") or "")


def _filename_from_image_ref(image_ref: str, task_id: int | str) -> str:
    """Turn LS image URLs into a safe filename stem (fixes ?d= Windows export bug)."""
    ref = unquote(image_ref)
    parsed = urlparse(ref if "://" in ref else f"http://local{ref}")

    if parsed.query:
        query = parse_qs(parsed.query)
        local_values = query.get("d") or query.get("path") or []
        if local_values:
            return _safe_stem(local_values[0])

    basename = Path(parsed.path.replace("\\", "/")).name
    if basename and basename not in ("", "local-files", "upload"):
        return _safe_stem(basename)

    return f"task_{task_id}"


def _resolve_local_image(image_ref: str, local_files_root: Path | None) -> Path | None:
    ref = unquote(image_ref)
    parsed = urlparse(ref if "://" in ref else f"http://local{ref}")

    candidates: list[Path] = []

    if parsed.query:
        query = parse_qs(parsed.query)
        for key in ("d", "path"):
            values = query.get(key) or []
            for value in values:
                rel = unquote(value).replace("\\", "/")
                if local_files_root:
                    candidates.append((local_files_root / rel).resolve())
                candidates.append((ROOT / rel).resolve())
                candidates.append(Path(rel).resolve())

    path_name = Path(parsed.path.replace("\\", "/")).name
    if path_name and local_files_root:
        candidates.append(local_files_root / path_name)
        candidates.extend(local_files_root.rglob(path_name))

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.is_file():
            return candidate
    return None


def _download_image(url: str, api_key: str, dest: Path) -> bool:
    headers = {"Authorization": f"Token {api_key}"} if api_key else {}
    try:
        resp = requests.get(url, headers=headers, timeout=120)
        resp.raise_for_status()
    except Exception as exc:
        print(f"  skip download {url}: {exc}")
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(resp.content)
    return True


def _annotation_results(task: dict) -> list[dict]:
    for key in ("annotations", "completions"):
        items = task.get(key) or []
        for item in items:
            if item.get("was_cancelled"):
                continue
            result = item.get("result") or []
            if result:
                return result
    predictions = task.get("predictions") or []
    for pred in predictions:
        result = pred.get("result") or []
        if result:
            return result
    return []


def _rect_to_yolo(value: dict) -> tuple[int, float, float, float, float] | None:
    labels = value.get("rectanglelabels") or value.get("labels") or []
    if not labels:
        return None
    label = str(labels[0]).lower()
    class_id = CLASS_TO_ID.get(label)
    if class_id is None:
        for name, cid in CLASS_TO_ID.items():
            if name in label:
                class_id = cid
                break
    if class_id is None:
        return None

    x = float(value.get("x", 0))
    y = float(value.get("y", 0))
    w = float(value.get("width", 0))
    h = float(value.get("height", 0))
    cx = (x + w / 2.0) / 100.0
    cy = (y + h / 2.0) / 100.0
    return class_id, cx, cy, w / 100.0, h / 100.0


def _fetch_export_json(url: str, project_id: int, api_key: str) -> list[dict]:
    base = url.rstrip("/")
    headers = {"Authorization": f"Token {api_key}"}
    export_resp = requests.post(
        f"{base}/api/projects/{project_id}/export",
        headers=headers,
        json={"exportType": "JSON"},
        timeout=120,
    )
    export_resp.raise_for_status()
    export_id = export_resp.json()["id"]

    while True:
        status_resp = requests.get(
            f"{base}/api/projects/{project_id}/exports/{export_id}",
            headers=headers,
            timeout=60,
        )
        status_resp.raise_for_status()
        payload = status_resp.json()
        if payload.get("status") == "completed":
            break
        if payload.get("status") == "failed":
            raise RuntimeError(f"Label Studio export failed: {payload}")

    file_resp = requests.get(
        f"{base}/api/projects/{project_id}/exports/{export_id}/download",
        headers=headers,
        timeout=300,
    )
    file_resp.raise_for_status()
    return json.loads(file_resp.content)


def _load_tasks(json_path: Path | None, url: str | None, project_id: int | None, api_key: str) -> list[dict]:
    if json_path:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else data.get("tasks") or [data]
    if url and project_id is not None and api_key:
        return _fetch_export_json(url, project_id, api_key)
    raise SystemExit("Provide --json or (--project-id, --url, --api-key).")


def export_yolo_dataset(
    tasks: list[dict],
    output: Path,
    local_files_root: Path | None,
    ls_url: str,
    api_key: str,
    val_ratio: float,
    seed: int,
) -> Path:
    if output.exists():
        shutil.rmtree(output)

    parsed: list[
        tuple[str, str, Path | None, list[tuple[int, float, float, float, float]]]
    ] = []
    used_names: dict[str, int] = {}

    for task in tasks:
        task_id = task.get("id", len(parsed))
        image_ref = _image_ref_from_task(task)
        if not image_ref:
            print(f"skip task {task_id}: no image")
            continue

        stem = _filename_from_image_ref(image_ref, task_id)
        if stem in used_names:
            used_names[stem] += 1
            stem = f"{stem}_{used_names[stem]}"
        else:
            used_names[stem] = 0

        boxes: list[tuple[int, float, float, float, float]] = []
        for item in _annotation_results(task):
            if item.get("type") != "rectanglelabels":
                continue
            row = _rect_to_yolo(item.get("value") or {})
            if row:
                boxes.append(row)

        image_path = _resolve_local_image(image_ref, local_files_root)
        parsed.append((stem, image_ref, image_path, boxes))

    if not parsed:
        raise SystemExit("No tasks with images found in export.")

    rng = random.Random(seed)
    shuffled = parsed[:]
    rng.shuffle(shuffled)
    val_n = max(1, int(round(len(shuffled) * val_ratio))) if len(shuffled) > 1 else 1
    val_set = set(id(item) for item in shuffled[:val_n])

    exported = 0
    for entry in parsed:
        stem, image_ref, image_path, boxes = entry
        split = "val" if id(entry) in val_set else "train"

        img_out = output / "images" / split / f"{stem}.jpg"
        lbl_out = output / "labels" / split / f"{stem}.txt"
        img_out.parent.mkdir(parents=True, exist_ok=True)
        lbl_out.parent.mkdir(parents=True, exist_ok=True)

        if image_path and image_path.is_file():
            shutil.copy2(image_path, img_out.with_suffix(image_path.suffix.lower()))
            img_out = img_out.with_suffix(image_path.suffix.lower())
        else:
            fetch_url = image_ref if image_ref.startswith("http") else f"{ls_url.rstrip('/')}{image_ref}"
            suffix = Path(unquote(image_ref)).suffix.lower() or ".jpg"
            img_out = output / "images" / split / f"{stem}{suffix}"
            if not _download_image(fetch_url, api_key, img_out):
                print(f"skip task {stem}: image not found (set --local-files-root)")
                continue

        lbl_out = output / "labels" / split / f"{img_out.stem}.txt"
        lines = [f"{cid} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}" for cid, cx, cy, bw, bh in boxes]
        lbl_out.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        exported += 1

    data_yaml = output / "data.yaml"
    data_yaml.write_text(
        "\n".join(
            [
                f"path: {output.resolve().as_posix()}",
                "train: images/train",
                "val: images/val",
                "names:",
                *[f"  {idx}: {name}" for idx, name in enumerate(CLASS_NAMES)],
                "",
            ]
        ),
        encoding="utf-8",
    )

    print(f"Exported {exported} images to {output}")
    print(f"data.yaml -> {data_yaml}")
    print("Train with: python train.py --epochs 50")
    return data_yaml


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=None, help="Label Studio JSON export file")
    parser.add_argument("--project-id", type=int, default=None)
    parser.add_argument("--url", default="http://localhost:8080")
    parser.add_argument("--api-key", default=os.environ.get("LABEL_STUDIO_API_KEY", ""))
    parser.add_argument(
        "--local-files-root",
        type=Path,
        default=None,
        help="Root folder used in Label Studio Local Files (resolves ?d=banana/DJI_0100.JPG)",
    )
    parser.add_argument("--output", type=Path, default=ROOT / "datasets" / "yolo_banana")
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    tasks = _load_tasks(args.json, args.url, args.project_id, args.api_key)
    local_root = args.local_files_root.resolve() if args.local_files_root else None
    export_yolo_dataset(
        tasks=tasks,
        output=args.output.resolve(),
        local_files_root=local_root,
        ls_url=args.url,
        api_key=args.api_key,
        val_ratio=args.val_ratio,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
