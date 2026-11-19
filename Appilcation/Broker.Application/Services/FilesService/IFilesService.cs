using Broker.Application.Contracts;
using File = Broker.Model.File;

namespace Broker.Application.Services.FilesService;

public interface IFilesService
{
    /// <summary>Сохраняет файл и ставит его в очередь на анализ нейросетью.</summary>
    Task AddFileAsync(
        File file,
        CancellationToken token);

    Task<FileScanningResult> GetFileStatus(
        Guid fileId,
        CancellationToken token);
}
