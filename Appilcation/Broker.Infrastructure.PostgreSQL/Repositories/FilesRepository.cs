using Broker.Application.Services.FilesService;
using Broker.Model.Enums;
using Microsoft.EntityFrameworkCore;
using File = Broker.Model.File;

namespace Broker.Infrastructure.PostgreSQL.Repositories;

internal class FilesRepository : IFilesRepository
{
    private readonly AppDbContext _dbContext;

    public async Task AddFileAsync(File file, CancellationToken token)
    {
        await _dbContext.Files.AddAsync(file, token);

        await _dbContext.SaveChangesAsync(token);
    }

    public async Task<File?> GetAsync(Guid id, CancellationToken token)
        => await _dbContext.Files.FirstOrDefaultAsync(f => f.Id == id, token);

    public async Task UpdateAsync(File file, CancellationToken token)
    {
        _dbContext.Files.Update(file);

        await _dbContext.SaveChangesAsync(token);
    }

    public async Task<List<Guid>> GetIdsByStatusAsync(IReadOnlyCollection<FileStatus> statuses, CancellationToken token)
        => await _dbContext.Files
            .Where(f => statuses.Contains(f.Status))
            .OrderBy(f => f.CreatedAt)
            .Select(f => f.Id)
            .ToListAsync(token);

    public FilesRepository(AppDbContext dbContext)
    {
        _dbContext = dbContext;
    }
}
