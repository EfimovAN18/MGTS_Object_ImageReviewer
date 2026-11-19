using Microsoft.AspNetCore.Mvc;

namespace Mgts.ModelApi;

[ApiController]
[Route("api/inspection")]
public class InspectionController(MgtsModelClient model) : ControllerBase
{
    // Режим «Изображение»: POST /api/inspection/image  (multipart, поле file)
    [HttpPost("image")]
    [RequestSizeLimit(20 * 1024 * 1024)]
    public async Task<ActionResult<FrameResult>> Image(IFormFile file, CancellationToken ct)
    {
        if (file.Length == 0) return BadRequest("Пустой файл");
        await using var s = file.OpenReadStream();
        return Ok(await model.AnalyzeImageAsync(s, file.FileName, ct));
    }

    // Режим «Видео»: POST /api/inspection/video  (multipart, поля file и interval)
    [HttpPost("video")]
    [RequestSizeLimit(500 * 1024 * 1024)]
    [RequestFormLimits(MultipartBodyLengthLimit = 500 * 1024 * 1024)]
    public async Task<ActionResult<VideoResult>> Video(IFormFile file, [FromForm] double interval = 5,
                                                       CancellationToken ct = default)
    {
        await using var s = file.OpenReadStream();
        return Ok(await model.AnalyzeVideoAsync(s, file.FileName, interval, ct));
    }

    // Режим «Трансляция»: фронт раз в N секунд берёт кадр с камеры (canvas.toBlob)
    // и шлёт его сюда — это тот же анализ одного изображения.
    [HttpPost("stream-frame")]
    [RequestSizeLimit(10 * 1024 * 1024)]
    public Task<ActionResult<FrameResult>> StreamFrame(IFormFile file, CancellationToken ct)
        => Image(file, ct);

    [HttpGet("health")]
    public async Task<IActionResult> Health(CancellationToken ct)
        => await model.IsHealthyAsync(ct) ? Ok("model online") : StatusCode(503, "model offline");
}
