using Broker.Application.Contracts;

namespace Broker.Application.Services.Inspection;

/// <summary>Нейросеть (Python API). Реализация — HTTP-клиент в проекте Broker.</summary>
public interface IInspectionModel
{
    Task<FrameResult> AnalyzeImageAsync(Stream image, string fileName, string mime, CancellationToken token);

    Task<VideoResult> AnalyzeVideoAsync(Stream video, string fileName, string mime, double intervalSec, CancellationToken token);

    Task<bool> IsHealthyAsync(CancellationToken token);
}
