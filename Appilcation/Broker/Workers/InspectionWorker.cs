using System.Text.Json;
using Broker.Application.Contracts;
using Broker.Application.MimeTypes;
using Broker.Application.Services.FilesService;
using Broker.Application.Services.Inspection;
using Broker.Model.Enums;

namespace Broker.Workers;

/// <summary>
/// Фоновый обработчик: берёт id файлов из очереди, отправляет файл в нейросеть,
/// сохраняет картинки с рамками на диск и результат в БД.
/// </summary>
public class InspectionWorker : BackgroundService
{
    private readonly IInspectionQueue _queue;
    private readonly IServiceScopeFactory _scopes;
    private readonly ILogger<InspectionWorker> _logger;
    private readonly double _videoIntervalSec;

    public InspectionWorker(IInspectionQueue queue, IServiceScopeFactory scopes,
                            ILogger<InspectionWorker> logger, IConfiguration configuration)
    {
        _queue = queue;
        _scopes = scopes;
        _logger = logger;
        _videoIntervalSec = configuration.GetValue<double?>("ModelApi:VideoIntervalSec") ?? 5;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        await RequeueUnfinishedAsync(stoppingToken);

        await foreach (var fileId in _queue.ReadAllAsync(stoppingToken))
        {
            try
            {
                await ProcessAsync(fileId, stoppingToken);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                break;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Не удалось обработать файл {FileId}", fileId);
            }
        }
    }

    /// <summary>После перезапуска досылаем в очередь то, что не успели проанализировать.</summary>
    private async Task RequeueUnfinishedAsync(CancellationToken token)
    {
        try
        {
            using var scope = _scopes.CreateScope();
            var repository = scope.ServiceProvider.GetRequiredService<IFilesRepository>();
            var ids = await repository.GetIdsByStatusAsync(new[] { FileStatus.Pending, FileStatus.Processing }, token);
            foreach (var id in ids)
                await _queue.EnqueueAsync(id, token);

            if (ids.Count > 0)
                _logger.LogInformation("Возвращено в очередь файлов: {Count}", ids.Count);
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            _logger.LogWarning(ex, "Не удалось восстановить очередь анализа");
        }
    }

    private async Task ProcessAsync(Guid fileId, CancellationToken token)
    {
        using var scope = _scopes.CreateScope();
        var repository = scope.ServiceProvider.GetRequiredService<IFilesRepository>();
        var model = scope.ServiceProvider.GetRequiredService<IInspectionModel>();

        var file = await repository.GetAsync(fileId, token);
        if (file is null)
            return;

        file.Status = FileStatus.Processing;
        await repository.UpdateAsync(file, token);

        try
        {
            List<FrameResult> frames;
            var fileName = Path.GetFileName(file.FullPath);

            await using (var stream = System.IO.File.OpenRead(file.FullPath))
            {
                if (VideoMime.IsValid(file.Mime))
                    frames = (await model.AnalyzeVideoAsync(stream, fileName, file.Mime, _videoIntervalSec, token)).Frames;
                else
                    frames = new List<FrameResult> { await model.AnalyzeImageAsync(stream, fileName, file.Mime, token) };
            }

            // картинки с рамками — на диск, в БД — только JSON без base64
            Directory.CreateDirectory(Storage.ResultsDir(fileId));
            for (int i = 0; i < frames.Count; i++)
            {
                if (frames[i].ImageB64 is { } b64)
                    await System.IO.File.WriteAllBytesAsync(Storage.FrameImagePath(fileId, i), Convert.FromBase64String(b64), token);
            }

            var stored = frames.Select(f => f with { ImageB64 = null }).ToList();
            file.ResultJson = JsonSerializer.Serialize(stored, ModelJson.Options);
            file.Status = InspectionSummary.ToFileStatus(stored);
            file.Message = InspectionSummary.Describe(stored);
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            _logger.LogError(ex, "Ошибка анализа файла {FileId}", fileId);
            file.Status = FileStatus.Failed;
            file.Message = $"Ошибка анализа: {ex.Message}";
        }

        file.ProcessedAt = DateTime.UtcNow;
        await repository.UpdateAsync(file, token);
    }
}
