"""HTTP API для сайта.

    uvicorn app.api:app --host 0.0.0.0 --port 8000
    документация: http://localhost:8000/docs

POST /analyze/image   — файл изображения -> статус, объекты, картинка с рамками (base64 JPEG)
POST /analyze/video   — видеофайл (+ interval) -> то же по каждому кадру
WS   /analyze/stream  — клиент шлёт кадры (JPEG, бинарно), сервер отвечает JSON по каждому
"""
import base64
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.inspector import Inspector  # noqa: E402

app = FastAPI(title="MGTS Object Image Reviewer")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
inspector = Inspector()


def _b64(img) -> str:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buf).decode()


def _decode(data: bytes):
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(400, "Не удалось прочитать изображение")
    return img


@app.get("/health")
def health():
    return {"ok": True, "classifier_loaded": inspector.cls is not None}


@app.post("/analyze/image")
async def analyze_image(file: UploadFile = File(...)):
    res, annotated = inspector.analyze_image(_decode(await file.read()))
    return res.to_dict() | {"image_b64": _b64(annotated)}


@app.post("/analyze/video")
async def analyze_video(file: UploadFile = File(...), interval: float = Form(5.0)):
    suffix = Path(file.filename or "v.mp4").suffix or ".mp4"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        path = tmp.name
    try:
        frames = [r.to_dict() | {"image_b64": _b64(a)}
                  for r, a in inspector.analyze_video(path, interval)]
    finally:
        Path(path).unlink(missing_ok=True)
    attention = [f for f in frames if f["status"] in ("Не исправен", "Требует проверки", "Плохое качество снимка")]
    return {"frames": frames, "total": len(frames), "need_attention": len(attention)}


@app.websocket("/analyze/stream")
async def analyze_stream(ws: WebSocket):
    """Сайт сам берёт кадр с камеры раз в N секунд и отправляет его сюда."""
    await ws.accept()
    try:
        while True:
            data = await ws.receive_bytes()
            img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                await ws.send_json({"error": "bad frame"})
                continue
            res, annotated = inspector.analyze_image(img)
            await ws.send_json(res.to_dict() | {"image_b64": _b64(annotated)})
    except WebSocketDisconnect:
        pass
