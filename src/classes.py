"""Единая схема классов и сведение к ней чужих названий классов."""
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((ROOT / "configs" / "classes.yaml").read_text(encoding="utf-8"))

DET_NAMES = {int(k): v for k, v in CFG["detector"].items()}
DET_IDS = {v: k for k, v in DET_NAMES.items()}
CLS_NAMES = list(CFG["classifier"])
KW = CFG["keywords"]


def _has(name: str, words) -> bool:
    # совпадение с начала слова: "ok" не должно находиться внутри "broken"
    return any(re.search(r"\b" + re.escape(w), name) for w in words)


def _norm(s: str) -> str:
    return re.sub(r"[-_/.]+", " ", s.lower())


def map_class(name: str):
    """Чужое имя класса -> (тип объекта | None, состояние | None).

    Примеры: "Broken" -> ("manhole", "damaged") если датасет про люки;
    "utility-pole" -> ("pole", None).
    """
    n = _norm(name)
    obj = None
    if _has(n, KW["pole"]):
        obj = "pole"
    elif _has(n, KW["manhole"]):
        obj = "manhole"

    state = None
    if _has(n, KW["ok"]):
        state = "ok"
    elif _has(n, KW["damaged"]):
        state = "damaged"
    return obj, state


def guess_dataset_object(slug: str, class_names) -> str | None:
    """Тип объекта по умолчанию для датасета, если в имени класса его нет
    (например, класс просто "Broken" в датасете про люки)."""
    s = _norm(slug)
    if _has(s, KW["pole"]):
        return "pole"
    if _has(s, KW["manhole"]):
        return "manhole"
    for c in class_names:
        obj, _ = map_class(c)
        if obj:
            return obj
    return None
