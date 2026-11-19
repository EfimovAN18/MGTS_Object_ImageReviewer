using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;

namespace Mgts.ModelApi;

// ===== DTO: ответы Python API модели (app/api.py) =====

public record DetectedObject(
    string ObjectType,      // manhole | pole
    string ObjectName,      // Колодец | Опора
    double DetConf,         // уверенность детектора
    int[] Bbox,             // [x1, y1, x2, y2] в пикселях
    string Status,          // Исправен | Не исправен | Требует проверки | Не определено
    double? DamageProb);    // вероятность поломки (null, если состояние не оценивалось)

public record ImageQuality(
    bool Ok,                    // false — снимок плохой
    List<string> Issues,        // "снимок размыт", "слишком темно", "снимок засвечен", "слишком низкое разрешение"
    double Sharpness,
    double Brightness);

public record FrameResult(
    string Status,              // Исправен | Не исправен | Требует проверки | Объекты не найдены | Плохое качество снимка
    string? Message,            // пояснение для пользователя (например, «Переснимите объект»)
    double? TimestampS,         // секунда видео (для видео/трансляции)
    ImageQuality? Quality,
    List<DetectedObject> Objects,
    string? ImageB64);          // JPEG с рамками в base64

public record VideoResult(List<FrameResult> Frames, int Total, int NeedAttention);

// ===== Клиент =====

public class MgtsModelClient(HttpClient http)
{
    // Python API отдаёт snake_case: object_name, damage_prob, image_b64 ...
    private static readonly JsonSerializerOptions Json = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        PropertyNameCaseInsensitive = true,
    };

    public async Task<bool> IsHealthyAsync(CancellationToken ct = default)
    {
        try { return (await http.GetAsync("/health", ct)).IsSuccessStatusCode; }
        catch { return false; }
    }

    public Task<FrameResult> AnalyzeImageAsync(Stream image, string fileName, CancellationToken ct = default)
        => PostFileAsync<FrameResult>("/analyze/image", image, fileName, "image/jpeg", null, ct);

    public Task<VideoResult> AnalyzeVideoAsync(Stream video, string fileName, double intervalSec = 5,
                                               CancellationToken ct = default)
        => PostFileAsync<VideoResult>("/analyze/video", video, fileName, "video/mp4",
               new() { ["interval"] = intervalSec.ToString(System.Globalization.CultureInfo.InvariantCulture) }, ct);

    private async Task<T> PostFileAsync<T>(string url, Stream file, string fileName, string contentType,
                                           Dictionary<string, string>? fields, CancellationToken ct)
    {
        using var form = new MultipartFormDataContent();
        var fileContent = new StreamContent(file);
        fileContent.Headers.ContentType = new MediaTypeHeaderValue(contentType);
        form.Add(fileContent, "file", fileName);
        if (fields != null)
            foreach (var (k, v) in fields) form.Add(new StringContent(v), k);

        using var resp = await http.PostAsync(url, form, ct);
        if (!resp.IsSuccessStatusCode)
            throw new HttpRequestException(
                $"Model API {(int)resp.StatusCode}: {await resp.Content.ReadAsStringAsync(ct)}");
        return (await resp.Content.ReadFromJsonAsync<T>(Json, ct))!;
    }
}
