using Broker.Application.Services.FilesService;
using Broker.Infrastructure.PostgreSQL.Repositories;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Diagnostics;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;

namespace Broker.Infrastructure.PostgreSQL;

public static class DependenciesInjection
{
    /// <param name="configuration">
    /// Конфигурация приложения. Если в ней есть ConnectionStrings:DefaultConnection
    /// (appsettings / переменная окружения ConnectionStrings__DefaultConnection) — берётся она,
    /// иначе, как и раньше, user secrets.
    /// </param>
    public static IServiceCollection AddPostgreSQL(this IServiceCollection services, IConfiguration? configuration = null)
    {
        services.AddDbContext<AppDbContext>(options => 
        {
            var connectionString = configuration?.GetConnectionString("DefaultConnection");

            if (string.IsNullOrWhiteSpace(connectionString))
            {
                var secrets = new ConfigurationBuilder()
                           .AddUserSecrets<AppDbContext>()
                           .Build();

                connectionString = secrets.GetConnectionString("DefaultConnection");
            }

            options.UseNpgsql(connectionString);
            // миграции написаны вручную — не падать, если снапшот чуть отличается от модели
            options.ConfigureWarnings(w => w.Ignore(RelationalEventId.PendingModelChangesWarning));
        });

        services.AddScoped<IFilesRepository, FilesRepository>();

        return services;
    }
}
