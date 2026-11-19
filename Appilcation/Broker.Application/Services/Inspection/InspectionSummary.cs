using System.Globalization;
using Broker.Application.Contracts;
using Broker.Model.Enums;

namespace Broker.Application.Services.Inspection;

public static class InspectionSummary
{
    public static FileStatus ToFileStatus(IReadOnlyList<FrameResult> frames)
        => frames.Any(f => f.NeedsAttention) ? FileStatus.HasProblems : FileStatus.Ok;

    /// <summary>Короткий текст для пользователя.</summary>
    public static string Describe(IReadOnlyList<FrameResult> frames)
    {
        if (frames.Count == 0)
            return "Не удалось получить кадры для анализа";

        if (frames.Count > 1)
        {
            int bad = frames.Count(f => f.NeedsAttention);
            return $"Проанализировано кадров: {frames.Count}, требуют внимания: {bad}";
        }

        var frame = frames[0];
        if (frame.Message is not null)
            return frame.Message;
        if (frame.Objects.Count == 0)
            return "Объекты не найдены";

        return string.Join("; ", frame.Objects.Select(o => o.DamageProb is double p
            ? $"{o.ObjectName}: {o.Status} ({p.ToString("0.00", CultureInfo.InvariantCulture)})"
            : $"{o.ObjectName}: {o.Status}"));
    }

    public static string DefaultMessage(FileStatus status) => status switch
    {
        FileStatus.Pending => "В очереди на анализ",
        FileStatus.Processing => "Анализируется нейросетью",
        FileStatus.Ok => "Проблем не найдено",
        FileStatus.HasProblems => "Найдены проблемы",
        FileStatus.Failed => "Ошибка анализа",
        _ => "This file does not exists!"
    };
}
