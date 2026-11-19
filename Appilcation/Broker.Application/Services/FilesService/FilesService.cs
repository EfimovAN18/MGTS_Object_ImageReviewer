using System.Text.Json;
using Broker.Application.Contracts;
using Broker.Application.Services.Inspection;
using Broker.Model.Enums;
using File = Broker.Model.File;

namespace Broker.Application.Services.FilesService;

public class FilesService : IFilesService
{
    private readonly IFilesRepository _filesRepository;
    private readonly IInspectionQueue _queue;

    public async Task AddFileAsync(
        File file,
        CancellationToken token)
    {
        file.Status = FileStatus.Pending;
        file.CreatedAt = DateTime.UtcNow;

        await _filesRepository.AddFileAsync(file, token);
        await _queue.EnqueueAsync(file.Id, token);
    }

    public async Task<FileScanningResult> GetFileStatus(Guid fileId, CancellationToken token)
    {
        var file = await _filesRepository.GetAsync(fileId, token);
        if (file == null)
            return new FileScanningResult(FileStatus.NotExists, "This file does not exists!");

        IReadOnlyList<FrameResult>? frames = file.ResultJson is null
            ? null
            : JsonSerializer.Deserialize<List<FrameResult>>(file.ResultJson, ModelJson.Options);

        return new FileScanningResult(
            file.Status,
            file.Message ?? InspectionSummary.DefaultMessage(file.Status),
            frames);
    }

    public FilesService(IFilesRepository filesRepository, IInspectionQueue queue)
    {
        _filesRepository = filesRepository;
        _queue = queue;
    }
}
