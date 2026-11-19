"""Обучение детектора YOLO11 (колодцы, опоры) на data/det.

    python scripts/03_train_detector.py                 # yolo11s, 100 эпох
    python scripts/03_train_detector.py --model yolo11m.pt --epochs 150

RTX 4070 Laptop (8 ГБ): yolo11s batch 16 / yolo11m batch 8 при imgsz 640.
Лучшие веса копируются в models/detector.pt.
"""
import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.classes import DET_NAMES  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="yolo11s.pt")
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--device", default="0", help="0 — первая видеокарта, cpu — без GPU")
    args = ap.parse_args()

    from ultralytics import YOLO

    det = ROOT / "data" / "det"
    yaml_path = det / "data.yaml"
    yaml_path.write_text(
        f"path: {det.as_posix()}\ntrain: images/train\nval: images/val\n"
        "names:\n" + "".join(f"  {k}: {v}\n" for k, v in DET_NAMES.items()),
        encoding="utf-8",
    )

    model = YOLO(args.model)
    model.train(
        data=str(yaml_path),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        patience=25,
        project=str(ROOT / "runs"),
        name="detector",
        exist_ok=True,
        # аугментации под съёмку с машины: погода, свет, смаз
        hsv_v=0.5, degrees=5, translate=0.1, scale=0.5, fliplr=0.5, mosaic=1.0, mixup=0.1,
    )
    best = ROOT / "runs" / "detector" / "weights" / "best.pt"
    shutil.copy2(best, ROOT / "models" / "detector.pt")
    metrics = YOLO(str(best)).val(data=str(yaml_path), device=args.device)
    print(f"mAP50={metrics.box.map50:.3f}  mAP50-95={metrics.box.map:.3f}  -> models/detector.pt")


if __name__ == "__main__":
    main()
