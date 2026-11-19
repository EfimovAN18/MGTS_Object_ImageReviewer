using System.Text.Json;
using System.Text.Json.Serialization;

namespace Broker.Application.Contracts;

// Ответы Python API нейросети (POST /analyze/image, /analyze/video).

public record DetectedObject(
    string ObjectType,      // manhole | pole
    string ObjectName,      // Колодец | Опора
    double DetConf,         // уверенность детектора
    int[] Bbox,             // [x1, y1, x2, y2] в пикселях
    string Status,          // текст: Исправен | Не исправен | Требует проверки | Не определено
    string StatusCode,      // ok | damaged | check | unknown
    bool IsDamaged,
    double? DamageProb);    // вероятность поломки 0..1

public record ImageQuality(
    bool Ok,
    List<string> Issues,    // "снимок размыт", "слишком темно", ...
    double Sharpness,
    double Brightness);

public record FrameResult(
    string Status,          // текст: Исправен | Не исправен | Требует проверки | Объекты не найдены | Плохое качество снимка
    string StatusCode,      // ok | damaged | check | unknown | no_objects | bad_photo
    bool NeedsAttention,
    string? Message,
    double? TimestampS,     // секунда видео
    ImageQuality? Quality,
    List<DetectedObject> Objects,
    [property: JsonPropertyName("image_b64")] string? ImageB64);  // JPEG с рамками (base64)

public record VideoResult(List<FrameResult> Frames, int Total, int NeedAttention);

public static class ModelJson
{
    /// <summary>Python API отдаёт snake_case — те же настройки используем для хранения в БД.</summary>
    public static readonly JsonSerializerOptions Options = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        PropertyNameCaseInsensitive = true,
    };
}
