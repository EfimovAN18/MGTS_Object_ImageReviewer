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
STATUS_BAD_PHOTO = "Плохое качество снимка"
STATUS_NOTHING = "Объекты не найдены"

# Пороги качества (подбираются на реальных снимках с камер)
BLUR_MIN = 60.0          # дисперсия Лапласиана: меньше — снимок размыт
DARK_MAX = 40.0          # средняя яркость: меньше — слишком темно
BRIGHT_MIN = 225.0       # средняя яркость: больше — засвечен
MIN_SIDE = 320           # px: меньше — слишком маленькое разрешение


def check_quality(img: np.ndarray) -> dict:
    """Быстрая проверка качества кадра до запуска нейросети."""
    h, w = img.shape[:2]
    scale = 640 / max(h, w)
    small = cv2.resize(img, (int(w * scale), int(h * scale))) if scale < 1 else img
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    bright = float(gray.mean())
    issues = []
    if blur < BLUR_MIN:
        issues.append("снимок размыт")
    if bright < DARK_MAX:
        issues.append("слишком темно")
    if bright > BRIGHT_MIN:
        issues.append("снимок засвечен")
    if min(h, w) < MIN_SIDE:
        issues.append("слишком низкое разрешение")
    return {"ok": not issues, "issues": issues,
            "sharpness": round(blur, 1), "brightness": round(bright, 1)}
# Машиночитаемые коды статусов (для бэкенда — не сравнивать русские строки)
STATUS_CODE = {STATUS_OK: "ok", STATUS_BAD: "damaged", STATUS_CHECK: "check",
               STATUS_UNKNOWN: "unknown", STATUS_BAD_PHOTO: "bad_photo", STATUS_NOTHING: "no_objects"}
NEEDS_ATTENTION = {STATUS_BAD, STATUS_CHECK, STATUS_BAD_PHOTO}

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
    quality: dict | None = None
    message: str | None = None   # пояснение для пользователя

    def to_dict(self):
        objs = []
        for o in self.objects:
            d = asdict(o)
            d["status_code"] = STATUS_CODE.get(o.status, "unknown")
            d["is_damaged"] = o.status == STATUS_BAD
            objs.append(d)
        return {"status": self.status,
                "status_code": STATUS_CODE.get(self.status, "unknown"),
                "needs_attention": self.status in NEEDS_ATTENTION,
                "message": self.message, "timestamp_s": self.timestamp_s,
                "quality": self.quality, "objects": objs}


class Inspector:
    def __init__(self, detector=ROOT / "models" / "detector.pt",
                 classifier=ROOT / "models" / "classifier.pt",
                 det_conf=0.35, damaged_thr=0.6, ok_thr=0.6, device=None,
                 classify_types=("manhole",)):
        """damaged_thr / ok_thr — пороги уверенности классификатора.
        Между ними объект получает статус «Требует проверки»."""
        from ultralytics import YOLO

        self.det = YOLO(str(detector))
        self.cls = YOLO(str(classifier)) if Path(classifier).exists() else None
        self.det_conf, self.damaged_thr, self.ok_thr = det_conf, damaged_thr, ok_thr
        self.device = device
        # классификатор состояния обучен только на этих типах объектов;
        # для остальных статус «Не определено», пока нет размеченных данных
        self.classify_types = set(classify_types)
        if self.cls is not None:
            names = {v: k for k, v in self.cls.names.items()}
            self._dmg_idx = names["damaged"]
            self._ok_idx = names["ok"]

    # ---------- одно изображение ----------
    def analyze_image(self, img: np.ndarray, timestamp_s=None) -> tuple[FrameResult, np.ndarray]:
        quality = check_quality(img)
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
        idx = [i for i, m in enumerate(metas) if m[0] in self.classify_types]
        if self.cls is not None and idx:
            res = self.cls.predict([crops[i] for i in idx], device=self.device, verbose=False)
            for i, r in zip(idx, res):
                probs[i] = float(r.probs.data[self._dmg_idx])

        objects = []
        for (obj, conf, bbox), p in zip(metas, probs):
            objects.append(DetectedObject(obj, OBJ_RU.get(obj, obj), round(conf, 3), bbox,
                                          self._status(p), None if p is None else round(p, 3)))

        problems = ", ".join(quality["issues"])
        if not objects and not quality["ok"]:
            # ничего не нашли на плохом снимке — нельзя утверждать, что объектов нет
            frame_status = STATUS_BAD_PHOTO
            message = f"Не удалось проанализировать: {problems}. Переснимите объект."
        elif not objects:
            frame_status = STATUS_NOTHING
            message = "На снимке не найдено колодцев и опор."
        else:
            frame_status = max((o.status for o in objects), key=_SEVERITY.get)
            message = None
            if not quality["ok"]:
                # объекты нашли, но снимок плохой — «Исправен» не доверяем
                for o in objects:
                    if o.status == STATUS_OK:
                        o.status = STATUS_CHECK
                if frame_status == STATUS_OK:
                    frame_status = STATUS_CHECK
                message = f"Качество снимка низкое ({problems}), результат требует проверки."
        result = FrameResult(frame_status, objects, timestamp_s, quality, message)
        return result, self.draw(img, objects)

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
