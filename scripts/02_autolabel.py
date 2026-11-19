"""Авторазметка собственных фото (без рамок) с помощью Grounding DINO.

Ожидаемая структура (метка состояния = имя папки):
    data/raw/own/ok/*.jpg        — фото исправных объектов
    data/raw/own/damaged/*.jpg   — фото неисправных объектов
Фото без подпапки состояния тоже можно положить в data/raw/own/unknown/ —
они пойдут только в детектор.

Что делает:
  1. находит колодцы и опоры по текстовому запросу -> рамки в формате YOLO (data/det)
  2. вырезает найденные объекты и кладёт в data/cls/<split>/<ok|damaged>
  3. сохраняет превью с рамками в data/autolabel_preview — ОБЯЗАТЕЛЬНО пролистать
     и удалить/исправить плохие примеры (например, в CVAT)

    python scripts/02_autolabel.py --input data/raw/own --box-thr 0.35
"""
import argparse
import hashlib
import sys
from pathlib import Path

import cv2
import numpy as np
import torch
import yaml
from PIL import Image
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.classes import DET_IDS  # noqa: E402

DET = ROOT / "data" / "det"
CLS = ROOT / "data" / "cls"
PREVIEW = ROOT / "data" / "autolabel_preview"
IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
COLORS = {"manhole": (0, 200, 255), "pole": (255, 120, 0)}


def split_of(name: str, val_frac: float) -> str:
    # детерминированный сплит: одно и то же фото всегда в одной выборке
    h = int(hashlib.md5(name.encode()).hexdigest(), 16) % 1000
    return "val" if h < val_frac * 1000 else "train"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(ROOT / "data" / "raw" / "own"))
    ap.add_argument("--model", default="IDEA-Research/grounding-dino-base")
    ap.add_argument("--box-thr", type=float, default=0.35)
    ap.add_argument("--text-thr", type=float, default=0.25)
    ap.add_argument("--val-frac", type=float, default=0.15)
    args = ap.parse_args()

    from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor

    prompts = yaml.safe_load((ROOT / "configs" / "classes.yaml").read_text(encoding="utf-8"))["autolabel_prompts"]
    text = ". ".join(prompts.values()) + "."
    device = "cuda" if torch.cuda.is_available() else "cpu"
    processor = AutoProcessor.from_pretrained(args.model)
    model = AutoModelForZeroShotObjectDetection.from_pretrained(args.model).to(device).eval()
    print(f"Grounding DINO на {device}, запрос: {text!r}")

    src = Path(args.input)
    images = [p for p in src.rglob("*") if p.suffix.lower() in IMG_EXT]
    stats = {"images": 0, "boxes": 0, "empty": 0}
    for p in tqdm(images):
        state = p.parent.name if p.parent.name in ("ok", "damaged") else None
        pil = Image.open(p).convert("RGB")
        inputs = processor(images=pil, text=text, return_tensors="pt").to(device)
        with torch.no_grad():
            out = model(**inputs)
        res = processor.post_process_grounded_object_detection(
            out, inputs.input_ids, threshold=args.box_thr, text_threshold=args.text_thr,
            target_sizes=[pil.size[::-1]],
        )[0]
        labels = res.get("text_labels", res.get("labels"))

        W, H = pil.size
        lines, boxes = [], []
        for box, lab, score in zip(res["boxes"].tolist(), labels, res["scores"].tolist()):
            lab = str(lab).lower()
            obj = next((k for k, v in prompts.items() if k in lab or v.split()[0] in lab), None)
            if obj is None:
                continue
            x1, y1, x2, y2 = box
            if (x2 - x1) * (y2 - y1) > 0.9 * W * H:  # рамка на весь кадр — мусор
                continue
            lines.append(f"{DET_IDS[obj]} {(x1 + x2) / 2 / W:.6f} {(y1 + y2) / 2 / H:.6f} "
                         f"{(x2 - x1) / W:.6f} {(y2 - y1) / H:.6f}")
            boxes.append((obj, score, int(x1), int(y1), int(x2), int(y2)))

        name = f"own__{p.parent.name}__{p.stem}"
        if not lines:
            stats["empty"] += 1
            continue
        split = split_of(name, args.val_frac)
        (DET / "images" / split).mkdir(parents=True, exist_ok=True)
        (DET / "labels" / split).mkdir(parents=True, exist_ok=True)
        pil.save(DET / "images" / split / f"{name}.jpg", quality=95)
        (DET / "labels" / split / f"{name}.txt").write_text("\n".join(lines) + "\n")
        stats["images"] += 1
        stats["boxes"] += len(lines)

        img = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
        prev = img.copy()
        for k, (obj, score, x1, y1, x2, y2) in enumerate(boxes):
            cv2.rectangle(prev, (x1, y1), (x2, y2), COLORS[obj], 2)
            cv2.putText(prev, f"{obj} {score:.2f}", (x1, max(15, y1 - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLORS[obj], 2)
            if state:
                # ВНИМАНИЕ: метка состояния — на всё фото. Если на фото несколько
                # объектов, а сломан один, проверьте вырезки вручную.
                d = CLS / split / state
                d.mkdir(parents=True, exist_ok=True)
                dw, dh = int((x2 - x1) * 0.1), int((y2 - y1) * 0.1)  # тот же запас, что в 01 и в инференсе
                cv2.imwrite(str(d / f"{name}_{k}.jpg"),
                            img[max(0, y1 - dh):min(H, y2 + dh), max(0, x1 - dw):min(W, x2 + dw)])
        PREVIEW.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(PREVIEW / f"{name}.jpg"), prev)

    print(f"Размечено {stats['images']} фото ({stats['boxes']} рамок), "
          f"без находок: {stats['empty']}. Проверьте превью: {PREVIEW}")


if __name__ == "__main__":
    main()
