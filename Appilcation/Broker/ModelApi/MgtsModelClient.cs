using System.Globalization;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using Broker.Application.Contracts;
using Broker.Application.Services.Inspection;

namespace Broker.ModelApi;

/// <summary>HTTP-клиент к Python API нейросети (uvicorn app.api:app --port 8000).</summary>
public class MgtsModelClient : IInspectionModel
{
    private readonly HttpClient _http;

    public MgtsModelClient(HttpClient http)
    {
        _http = http;
    }

    public async Task<bool> IsHealthyAsync(CancellationToken token)
    {
        try
        {
            using var response = await _http.GetAsync("/health", token);
            return response.IsSuccessStatusCode;
        }
        catch (HttpRequestException)
        {
            return false;
        }
    }

    public Task<FrameResult> AnalyzeImageAsync(Stream image, string fileName, string mime, CancellationToken token)
        => PostFileAsync<FrameResult>("/analyze/image", image, fileName, mime, null, token);

    public Task<VideoResult> AnalyzeVideoAsync(Stream video, string fileName, string mime, double intervalSec, CancellationToken token)
        => PostFileAsync<VideoResult>("/analyze/video", video, fileName, mime,
            new Dictionary<string, string> { ["interval"] = intervalSec.ToString(CultureInfo.InvariantCulture) },
            token);

    private async Task<T> PostFileAsync<T>(string url, Stream file, string fileName, string mime,
                                           Dictionary<string, string>? fields, CancellationToken token)
    {
        using var form = new MultipartFormDataContent();

        var fileContent = new StreamContent(file);
        fileContent.Headers.ContentType = new MediaTypeHeaderValue(mime);
        form.Add(fileContent, "file", fileName);

        if (fields != null)
            foreach (var (key, value) in fields)
                form.Add(new StringContent(value), key);

        using var response = await _http.PostAsync(url, form, token);
        if (!response.IsSuccessStatusCode)
        {
            var body = await response.Content.ReadAsStringAsync(token);
            throw new HttpRequestException($"Нейросеть вернула {(int)response.StatusCode}: {body}");
        }

        return await response.Content.ReadFromJsonAsync<T>(ModelJson.Options, token)
               ?? throw new HttpRequestException("Нейросеть вернула пустой ответ");
    }
}
