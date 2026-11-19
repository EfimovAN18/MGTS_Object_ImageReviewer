using Broker.Model.Enums;

namespace Broker.Application.Contracts
{
    public record FileScanningResult(
        FileStatus Status,
        string Message,
        IReadOnlyList<FrameResult>? Frames = null
    );
}
