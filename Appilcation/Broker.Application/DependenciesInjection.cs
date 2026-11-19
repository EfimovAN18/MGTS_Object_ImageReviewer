using Broker.Application.Services.FilesService;
using Broker.Application.Services.Inspection;
using Microsoft.Extensions.DependencyInjection;

namespace Broker.Application
{
    public static class DependenciesInjection
    {
        public static IServiceCollection AddApplication(this IServiceCollection services)
        {
            services.AddScoped<IFilesService, FilesService>();
            services.AddSingleton<IInspectionQueue, InspectionQueue>();

            return services;
        }
    }
}
