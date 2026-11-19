// Фрагмент Program.cs — добавьте к своему проекту ASP.NET Core (.NET 8+).
using Mgts.ModelApi;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddControllers();

// Клиент к Python API модели. Адрес — из appsettings.json (ModelApi:BaseUrl).
builder.Services.AddHttpClient<MgtsModelClient>(c =>
{
    c.BaseAddress = new Uri(builder.Configuration["ModelApi:BaseUrl"] ?? "http://localhost:8000");
    c.Timeout = TimeSpan.FromMinutes(10); // видео обрабатывается долго
});

// Видео бывают большими
builder.WebHost.ConfigureKestrel(o => o.Limits.MaxRequestBodySize = 500 * 1024 * 1024);

builder.Services.AddCors(o => o.AddDefaultPolicy(p => p.AllowAnyOrigin().AllowAnyHeader().AllowAnyMethod()));

var app = builder.Build();
app.UseCors();
app.MapControllers();
app.Run();
