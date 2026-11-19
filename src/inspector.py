"""Основной пайплайн: кадр -> детектор -> вырезка объекта -> классификатор -> рамки + статус.

Три режима из схемы проекта:
  analyze_image(img)                      — одно изображение
  analyze_video(path, interval_s=5)       — видео, кадр каждые N секунд
  analyze_stream(source, interval_s=5)    — трансляция (веб-камера, RTSP, URL)
"""
from dataclasses import asdict, dataclass, field
from pathlib import Path
import time

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]

STATUS_OK = "Исправен"
STATUS_BAD = "Не исправен"
STATUS_CHECK = "Требует проверки"
STATUS_UNKNOWN = "Не определено"
_SEVERITY = {STATUS_BAD: 3, STATUS_CHECK: 2, STATUS_UNKNOWN: 1, STATUS_OK: 0}
OBJ_RU = {"manhole": "Колодец", "pole": "Опора"}
# цвета BGR: зелёный / красный / жёлтый / серый
_COLOR = {STATUS_OK: (60, 180, 75), STATUS_BAD: (40, 40, 230),
          STATUS_CHECK: (0, 200, 255), STATUS_UNKNOWN: (160, 160, 160)}
_SHORT = {STATUS_OK: "OK", STATUS_BAD: "DAMAGED", STATUS_CHECK: "CHECK", STATUS_UNKNOWN: "?"}


@dataclass
class DetectedObject:
    object_type: str          # manhole | pole
    object_name: str          # Колодец | Опора
    det_conf: float
    bbox: list                # [x1, y1, x2, y2] в пикселях
    status: str               # Исправен | Не исправен | Требует проверки | Не определено
    damage_prob: float | None


@dataclass
class FrameResult:
    status: str
    objects: list = field(default_factory=list)
    timestamp_s: float | None = None

    def to_dict(self):
        return {"status": self.status, "timestamp_s": self.timestamp_s,
                "objects": [asdict(o) for o in self.objects]}


class Inspector:
    def __init__(self, detector=ROOT / "models" / "detector.pt",
                 classifier=ROOT / "models" / "classifier.pt",
                 det_conf=0.35, damaged_thr=0.6, ok_thr=0.6, device=None):
        """damaged_thr / ok_thr — пороги уверенности классификатора.
        Между ними объект получает статус «Требует проверки»."""
        from ultralytics import YOLO

        self.det = YOLO(str(detector))
        self.cls = YOLO(str(classifier)) if Path(classifier).exists() else None
        self.det_conf, self.damaged_thr, self.ok_thr = det_conf, damaged_thr, ok_thr
        self.device = device
        if self.cls is not None:
            names = {v: k for k, v in self.cls.names.items()}
            self._dmg_idx = names["damaged"]
            self._ok_idx = names["ok"]

    # ---------- одно изображение ----------
    def analyze_image(self, img: np.ndarray, timestamp_s=None) -> tuple[FrameResult, np.ndarray]:
        det = self.det.predict(img, conf=self.det_conf, device=self.device, verbose=False)[0]
        H, W = img.shape[:2]
        boxes = det.boxes.xyxy.cpu().numpy().astype(int) if len(det.boxes) else np.zeros((0, 4), int)
        crops, metas = [], []
        for (x1, y1, x2, y2), c, conf in zip(boxes, det.boxes.cls.tolist(), det.boxes.conf.tolist()):
            obj = det.names[int(c)]
            # тот же запас 20%, что и при подготовке датасета
            dw, dh = int((x2 - x1) * 0.1), int((y2 - y1) * 0.1)
            crop = img[max(0, y1 - dh):min(H, y2 + dh), max(0, x1 - dw):min(W, x2 + dw)]
            crops.append(crop)
            metas.append((obj, float(conf), [int(x1), int(y1), int(x2), int(y2)]))

        probs = [None] * len(crops)
        if self.cls is not None and crops:
            for i, r in enumerate(self.cls.predict(crops, device=self.device, verbose=False)):
                probs[i] = float(r.probs.data[self._dmg_idx])

        objects = []
        for (obj, conf, bbox), p in zip(metas, probs):
            objects.append(DetectedObject(obj, OBJ_RU.get(obj, obj), round(conf, 3), bbox,
                                          self._status(p), None if p is None else round(p, 3)))

        if not objects:
            frame_status = "Объекты не найдены"
        else:
            frame_status = max((o.status for o in objects), key=_SEVERITY.get)
        return FrameResult(frame_status, objects, timestamp_s), self.draw(img, objects)

    def _status(self, p_damaged):
        if p_damaged is None:
            return STATUS_UNKNOWN
        if p_damaged >= self.damaged_thr:
            return STATUS_BAD
        if 1 - p_damaged >= self.ok_thr:
            return STATUS_OK
        return STATUS_CHECK

    @staticmethod
    def draw(img, objects):
        out = img.copy()
        for o in objects:
            x1, y1, x2, y2 = o.bbox
            col = _COLOR[o.status]
            cv2.rectangle(out, (x1, y1), (x2, y2), col, 3)
            label = f"{o.object_type} {_SHORT[o.status]}"
            if o.damage_prob is not None:
                label += f" p={o.damage_prob:.2f}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            y = max(th + 6, y1)
            cv2.rectangle(out, (x1, y - th - 6), (x1 + tw + 6, y), col, -1)
            cv2.putText(out, label, (x1 + 3, y - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        return out

    # ---------- видео ----------
    def analyze_video(self, path, interval_s=5.0):
        """Генератор (FrameResult, annotated_frame) — кадр каждые interval_s секунд."""
        cap = cv2.VideoCapture(str(path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        step = max(1, int(round(fps * interval_s)))
        try:
            for idx in range(0, total, step):
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ok, frame = cap.read()
                if not ok:
                    break
                yield self.analyze_image(frame, timestamp_s=round(idx / fps, 2))
        finally:
            cap.release()

    # ---------- трансляция ----------
    def analyze_stream(self, source=0, interval_s=5.0, max_frames=None):
        """source: индекс веб-камеры, RTSP/HTTP URL. Берёт свежий кадр раз в interval_s секунд."""
        cap = cv2.VideoCapture(source)
        t0, last, n = time.time(), -interval_s, 0
        try:
            while cap.isOpened():
                ok, frame = cap.read()  # читаем всё подряд, чтобы буфер не отставал
                if not ok:
                    break
                now = time.time() - t0
                if now - last >= interval_s:
                    last = now
                    yield self.analyze_image(frame, timestamp_s=round(now, 2))
                    n += 1
                    if max_frames and n >= max_frames:
                        break
        finally:
            cap.release()
