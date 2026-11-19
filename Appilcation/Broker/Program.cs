using System.Text.Json.Serialization;
using Broker;
using Broker.Application;
using Broker.Application.MimeTypes;
using Broker.Application.Services.FilesService;
using Broker.Application.Services.Inspection;
using Broker.Infrastructure.PostgreSQL;
using Broker.ModelApi;
using Broker.Model.Enums;
using Broker.Workers;
using Microsoft.AspNetCore.Http.Features;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using File = Broker.Model.File;

public partial class Program
{
    private static void Main(string[] args)
    {
        var builder = WebApplication.CreateBuilder(args);

        builder.Services.AddSwaggerGen();
        builder.Services.AddAntiforgery();
        builder.Services.AddCors(o => o.AddDefaultPolicy(p => p.AllowAnyOrigin().AllowAnyHeader().AllowAnyMethod()));

        // статусы в JSON строками: "Ok", "HasProblems", "Pending" ... вместо чисел
        builder.Services.ConfigureHttpJsonOptions(o => o.SerializerOptions.Converters.Add(new JsonStringEnumConverter()));

        // загрузка видео
        builder.WebHost.ConfigureKestrel(o => o.Limits.MaxRequestBodySize = 500L * 1024 * 1024);
        builder.Services.Configure<FormOptions>(o => o.MultipartBodyLengthLimit = 500L * 1024 * 1024);

        builder.Services.AddApplication();
        builder.Services.AddPostgreSQL(builder.Configuration);

        // нейросеть: Python API (uvicorn app.api:app --port 8000)
        builder.Services.AddHttpClient<IInspectionModel, MgtsModelClient>(client =>
        {
            client.BaseAddress = new Uri(builder.Configuration["ModelApi:BaseUrl"] ?? "http://localhost:8000");
            client.Timeout = TimeSpan.FromMinutes(10); // видео анализируется долго
        });
        builder.Services.AddHostedService<InspectionWorker>();

        var app = builder.Build();

        using (var scope = app.Services.CreateScope())
        {
            var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();

            db.Database.Migrate();
        }

        if (app.Environment.IsDevelopment())
        {
            app.UseSwagger();
            app.UseSwaggerUI();
        }

        app.UseCors();
        app.UseAntiforgery();

        // 1. Загрузка фото/видео -> 202 + id. Анализ идёт в фоне (InspectionWorker).
        app.MapPost("api/files/upload", async (IFormFile formFile, HttpContext context, [FromServices] IFilesService service, CancellationToken token) =>
        {
            if (!RasterMime.IsValid(formFile.ContentType) && !VideoMime.IsValid(formFile.ContentType))
                return Results.StatusCode(415);

            Directory.CreateDirectory(Storage.PhotosDir);

            File file = new File
            {
                Id = Guid.NewGuid(),

                Mime = formFile.ContentType
            };
            file.FullPath = Path.Combine(Storage.PhotosDir, $"{file.Id}{file.Extension}");

            using (var stream = System.IO.File.Create(file.FullPath))
            {
                await formFile.CopyToAsync(stream, token);
            }

            await service.AddFileAsync(file, token);

            return Results.Accepted($"{context.Request.Scheme}://{context.Request.Host}/api/files/upload/{file.Id}", file.Id);
        }).DisableAntiforgery();

        // 2. Статус и результат анализа. Опрашивать, пока status = Pending / Processing.
        app.MapGet("api/files/upload/{id}", async ([FromRoute] Guid id, HttpContext context, [FromServices] IFilesService service, CancellationToken token) =>
        {
            var result = await service.GetFileStatus(id, token);
            if (result.Status == FileStatus.NotExists)
                return Results.NotFound(result);

            var baseUrl = $"{context.Request.Scheme}://{context.Request.Host}";
            var frameImages = result.Frames?
                .Select((_, i) => $"{baseUrl}/api/files/{id}/frames/{i}")
                .ToList();

            return Results.Ok(new
            {
                result.Status,
                result.Message,
                Frames = result.Frames,
                FrameImages = frameImages // картинки с рамками, по одной на кадр
            });
        });

        // 3. Картинка с рамками для кадра N
        app.MapGet("api/files/{id}/frames/{index:int}", ([FromRoute] Guid id, [FromRoute] int index) =>
        {
            var path = Storage.FrameImagePath(id, index);
            return System.IO.File.Exists(path)
                ? Results.File(path, "image/jpeg")
                : Results.NotFound();
        });

        // 4. Трансляция: фронт раз в N секунд шлёт кадр с камеры, ответ сразу (без очереди и БД)
        app.MapPost("api/stream/frame", async (IFormFile formFile, [FromServices] IInspectionModel model, CancellationToken token) =>
        {
            if (!RasterMime.IsValid(formFile.ContentType))
                return Results.StatusCode(415);

            await using var stream = formFile.OpenReadStream();
            var frame = await model.AnalyzeImageAsync(stream, formFile.FileName, formFile.ContentType, token);
            return Results.Ok(frame);
        }).DisableAntiforgery();

        // 5. Проверка, что нейросеть запущена
        app.MapGet("api/model/health", async ([FromServices] IInspectionModel model, CancellationToken token) =>
            await model.IsHealthyAsync(token)
                ? Results.Ok("model online")
                : Results.Problem("Нейросеть недоступна", statusCode: 503));

        app.Run();
    }
}
