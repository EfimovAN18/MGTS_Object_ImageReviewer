"""Скачивает открытые датасеты с Roboflow Universe и сводит их к единой схеме.

Результат:
  data/det/images/{train,val}, data/det/labels/{train,val}  — для детектора
  data/cls/{train,val}/{ok,damaged}                           — вырезанные объекты для классификатора

Нужен бесплатный API-ключ Roboflow: https://app.roboflow.com/settings/api
    set ROBOFLOW_API_KEY=xxxx        (Windows)
    export ROBOFLOW_API_KEY=xxxx     (Linux/macOS)
    python scripts/01_download_datasets.py
"""
import os
import shutil
import sys
from pathlib import Path

import cv2
import yaml
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.classes import DET_IDS, guess_dataset_object, is_ignored, map_class  # noqa: E402

RAW = ROOT / "data" / "raw" / "roboflow"
DET = ROOT / "data" / "det"
CLS = ROOT / "data" / "cls"
IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
MIN_CROP = 24  # px — слишком мелкие объекты в классификатор не берём


def download(slug: str) -> Path | None:
    from roboflow import Roboflow

    ws, proj = slug.split("/")
    out = RAW / slug.replace("/", "__")
    if (out / "data.yaml").exists():
        print(f"[skip] {slug} уже скачан")
        return out
    try:
        rf = Roboflow(api_key=os.environ["ROBOFLOW_API_KEY"])
        project = rf.workspace(ws).project(proj)
        version = max(project.versions(), key=lambda v: int(str(v.version).split("/")[-1]))
        version.download("yolov8", location=str(out), overwrite=True)
        return out
    except Exception as e:  # датасет удалён, приватный и т.п.
        print(f"[fail] {slug}: {e}")
        return None


def parse_line(line: str):
    """YOLO bbox или полигон -> (cls, xc, yc, w, h) в долях."""
    p = line.split()
    if len(p) < 5:
        return None
    c = int(float(p[0]))
    vals = list(map(float, p[1:]))
    if len(vals) == 4:
        return (c, *vals)
    xs, ys = vals[0::2], vals[1::2]  # сегментация -> рамка
    x1, x2, y1, y2 = min(xs), max(xs), min(ys), max(ys)
    return c, (x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1


def convert(ds_dir: Path, slug: str, stats: dict):
    meta = yaml.safe_load((ds_dir / "data.yaml").read_text(encoding="utf-8"))
    names = meta["names"]
    if isinstance(names, dict):
        names = [names[k] for k in sorted(names)]
    default_obj = guess_dataset_object(slug, names)
    mapping = {}
    for i, n in enumerate(names):
        if is_ignored(n):
            mapping[i] = (None, None)
            continue
        obj, state = map_class(n)
        mapping[i] = (obj or default_obj, state)
    print(f"  классы {slug}: " + ", ".join(f"{n}->{mapping[i]}" for i, n in enumerate(names)))

    prefix = slug.replace("/", "__")
    for split_src in ("train", "valid", "test"):
        img_dir = ds_dir / split_src / "images"
        if not img_dir.exists():
            continue
        split = "train" if split_src == "train" else "val"
        for img_path in tqdm(list(img_dir.iterdir()), desc=f"{slug}:{split_src}", leave=False):
            if img_path.suffix.lower() not in IMG_EXT:
                continue
            lbl_path = ds_dir / split_src / "labels" / (img_path.stem + ".txt")
            lines = lbl_path.read_text().splitlines() if lbl_path.exists() else []
            out_lines, crops = [], []
            for ln in lines:
                parsed = parse_line(ln)
                if not parsed:
                    continue
                c, xc, yc, w, h = parsed
                obj, state = mapping.get(c, (None, None))
                if obj is None:
                    continue
                out_lines.append(f"{DET_IDS[obj]} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}")
                if state:
                    crops.append((state, xc, yc, w, h))
            if not out_lines:
                continue

            name = f"{prefix}__{img_path.stem}"
            (DET / "images" / split).mkdir(parents=True, exist_ok=True)
            (DET / "labels" / split).mkdir(parents=True, exist_ok=True)
            shutil.copy2(img_path, DET / "images" / split / f"{name}{img_path.suffix}")
            (DET / "labels" / split / f"{name}.txt").write_text("\n".join(out_lines) + "\n")
            stats["det"] += 1

            if crops:
                img = cv2.imread(str(img_path))
                if img is None:
                    continue
                H, W = img.shape[:2]
                for k, (state, xc, yc, w, h) in enumerate(crops):
                    # небольшой запас вокруг объекта — контекст помогает классификатору
                    x1 = int(max(0, (xc - w * 0.6) * W)); x2 = int(min(W, (xc + w * 0.6) * W))
                    y1 = int(max(0, (yc - h * 0.6) * H)); y2 = int(min(H, (yc + h * 0.6) * H))
                    if x2 - x1 < MIN_CROP or y2 - y1 < MIN_CROP:
                        continue
                    d = CLS / split / state
                    d.mkdir(parents=True, exist_ok=True)
                    cv2.imwrite(str(d / f"{name}_{k}.jpg"), img[y1:y2, x1:x2])
                    stats[state] += 1


def main():
    if "ROBOFLOW_API_KEY" not in os.environ:
        sys.exit("Задайте переменную окружения ROBOFLOW_API_KEY (см. docstring).")
    slugs = yaml.safe_load((ROOT / "configs" / "datasets.yaml").read_text(encoding="utf-8"))["roboflow"]
    stats = {"det": 0, "ok": 0, "damaged": 0}
    for slug in slugs:
        d = download(slug)
        if d:
            convert(d, slug, stats)
    print(f"\nГотово: {stats['det']} изображений для детектора, "
          f"{stats['ok']} исправных и {stats['damaged']} неисправных объектов для классификатора.")


if __name__ == "__main__":
    main()
