using Microsoft.EntityFrameworkCore;
using File = Broker.Model.File;

namespace Broker.Infrastructure.PostgreSQL;

public class AppDbContext : DbContext
{
    public DbSet<File> Files { get; set; }

    public AppDbContext(DbContextOptions options) : base(options)
    {
                
    }
}
