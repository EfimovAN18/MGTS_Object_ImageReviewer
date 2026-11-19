using Broker.Model.Enums;
using File = Broker.Model.File;

namespace Broker.Application.Services.FilesService;

public interface IFilesRepository
{
    Task AddFileAsync(File file, CancellationToken token);

    Task<File?> GetAsync(Guid id, CancellationToken token);

    Task UpdateAsync(File file, CancellationToken token);

    Task<List<Guid>> GetIdsByStatusAsync(IReadOnlyCollection<FileStatus> statuses, CancellationToken token);
}
