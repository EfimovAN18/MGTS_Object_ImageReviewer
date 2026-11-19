"""Обучение классификатора состояния YOLO11-cls (ok / damaged) на data/cls.

    python scripts/04_train_classifier.py

Неисправных примеров обычно меньше — перед обучением скрипт печатает баланс
классов и при сильном перекосе дублирует редкий класс (oversampling).
Лучшие веса копируются в models/classifier.pt.
"""
import argparse
import random
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.classes import CLS_NAMES  # noqa: E402

CLS = ROOT / "data" / "cls"


def balance(split_dir: Path, max_ratio: float = 2.0):
    counts = {c: len(list((split_dir / c).glob("*.jpg"))) for c in CLS_NAMES}
    print(f"  {split_dir.name}: {counts}")
    if min(counts.values()) == 0:
        sys.exit(f"В {split_dir} нет примеров одного из классов — нечего учить.")
    big = max(counts.values())
    for c, n in counts.items():
        if big / n > max_ratio:
            files = list((split_dir / c).glob("*.jpg"))
            need = int(big / max_ratio) - n
            for i in range(need):
                src = random.choice(files)
                shutil.copy2(src, src.with_name(f"{src.stem}__dup{i}.jpg"))
            print(f"  oversampling {c}: +{need}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="yolo11s-cls.pt")
    ap.add_argument("--epochs", type=int, default=50)
    ap.add_argument("--imgsz", type=int, default=224)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--device", default="0")
    args = ap.parse_args()

    from ultralytics import YOLO

    print("Баланс классов:")
    balance(CLS / "train")
    for c in CLS_NAMES:
        (CLS / "val" / c).mkdir(parents=True, exist_ok=True)

    model = YOLO(args.model)
    model.train(
        data=str(CLS),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        patience=15,
        project=str(ROOT / "runs"),
        name="classifier",
        exist_ok=True,
    )
    best = ROOT / "runs" / "classifier" / "weights" / "best.pt"
    shutil.copy2(best, ROOT / "models" / "classifier.pt")
    metrics = YOLO(str(best)).val(data=str(CLS), device=args.device)
    print(f"top1 accuracy={metrics.top1:.3f}  -> models/classifier.pt")


if __name__ == "__main__":
    main()
