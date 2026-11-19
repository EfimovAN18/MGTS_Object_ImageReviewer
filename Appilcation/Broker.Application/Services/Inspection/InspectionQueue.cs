using System.Threading.Channels;

namespace Broker.Application.Services.Inspection;

public interface IInspectionQueue
{
    ValueTask EnqueueAsync(Guid fileId, CancellationToken token = default);

    IAsyncEnumerable<Guid> ReadAllAsync(CancellationToken token);
}

/// <summary>Очередь файлов на анализ. Загрузка отвечает сразу (202), анализ идёт в фоне.</summary>
public class InspectionQueue : IInspectionQueue
{
    private readonly Channel<Guid> _channel = Channel.CreateUnbounded<Guid>();

    public ValueTask EnqueueAsync(Guid fileId, CancellationToken token = default)
        => _channel.Writer.WriteAsync(fileId, token);

    public IAsyncEnumerable<Guid> ReadAllAsync(CancellationToken token)
        => _channel.Reader.ReadAllAsync(token);
}
