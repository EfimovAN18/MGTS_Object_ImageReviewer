# Подключение модели к бэкенду на .NET

```
Фронт → ASP.NET Core (InspectionController) → MgtsModelClient → Python API модели (:8000)
```

## 1. Запустить модель

В корне репозитория (веса лежат в `models/`):

```
uvicorn app.api:app --host 0.0.0.0 --port 8000
```

Проверка: http://localhost:8000/docs

## 2. Добавить в проект .NET (8+)

1. Скопируйте `MgtsModelClient.cs` и `InspectionController.cs` в свой проект.
2. Добавьте в `Program.cs` строки из `Program.example.cs` (регистрация `AddHttpClient<MgtsModelClient>`).
3. Добавьте в `appsettings.json` секцию `ModelApi:BaseUrl` (см. `appsettings.example.json`).

## 3. Эндпоинты бэкенда

| Режим | Запрос | Ответ |
|---|---|---|
| Изображение | `POST /api/inspection/image`, form-data `file` | `FrameResult` |
| Видео | `POST /api/inspection/video`, form-data `file`, `interval` | `VideoResult` |
| Трансляция | `POST /api/inspection/stream-frame` раз в N сек, кадр с камеры | `FrameResult` |
| Проверка | `GET /api/inspection/health` | 200 / 503 |

`FrameResult`: `status`, `objects[]` (`objectName`, `status`, `bbox`, `damageProb`), `imageB64`: картинка с рамками.

Показать картинку на фронте:

```html
<img src="data:image/jpeg;base64,{imageB64}">
```

Трансляция с камеры на фронте (каждые 5 секунд):

```js
setInterval(() => {
  canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
  canvas.toBlob(async blob => {
    const form = new FormData();
    form.append("file", blob, "frame.jpg");
    const r = await fetch("/api/inspection/stream-frame", { method: "POST", body: form });
    show(await r.json());
  }, "image/jpeg", 0.85);
}, 5000);
```
