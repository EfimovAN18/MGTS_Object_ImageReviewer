"""Запуск из командной строки.

    python -m src.cli image photo.jpg
    python -m src.cli video ride.mp4 --interval 5
    python -m src.cli stream 0 --interval 5            # веб-камера
    python -m src.cli stream rtsp://camera/stream

Картинки с рамками и report.json сохраняются в outputs/<имя>/.
"""
import argparse
import json
from pathlib import Path

import cv2

from src.inspector import Inspector

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["image", "video", "stream"])
    ap.add_argument("source")
    ap.add_argument("--interval", type=float, default=5.0, help="интервал между кадрами, сек")
    ap.add_argument("--max-frames", type=int, default=None)
    ap.add_argument("--det-conf", type=float, default=0.35)
    args = ap.parse_args()

    insp = Inspector(det_conf=args.det_conf)
    name = Path(args.source).stem if args.mode != "stream" else "stream"
    out_dir = ROOT / "outputs" / name
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.mode == "image":
        results = [insp.analyze_image(cv2.imread(args.source))]
    elif args.mode == "video":
        results = insp.analyze_video(args.source, args.interval)
    else:
        src = int(args.source) if args.source.isdigit() else args.source
        results = insp.analyze_stream(src, args.interval, args.max_frames)

    report = []
    for i, (res, annotated) in enumerate(results):
        fname = f"frame_{i:04d}.jpg"
        cv2.imwrite(str(out_dir / fname), annotated)
        d = res.to_dict() | {"frame": fname}
        report.append(d)
        objs = ", ".join(f"{o['object_name']}: {o['status']}" for o in d["objects"]) or "—"
        t = f"[{res.timestamp_s}s] " if res.timestamp_s is not None else ""
        print(f"{t}{res.status} | {objs}")

    (out_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    bad = [r for r in report if r["status"] in ("Не исправен", "Требует проверки")]
    print(f"\nКадров: {len(report)}, требуют внимания: {len(bad)}. Результаты: {out_dir}")


if __name__ == "__main__":
    main()
