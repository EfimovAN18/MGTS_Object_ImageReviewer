using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;
using Broker.Model.Enums;

namespace Broker.Model;

public class File
{
    [Key]
    public Guid Id { get; set; }

    public required string Mime { get; set; }

    public string FullPath { get; set; } = string.Empty;

    /// <summary>Статус анализа нейросетью.</summary>
    public FileStatus Status { get; set; } = FileStatus.Pending;

    /// <summary>Короткое пояснение для пользователя (что найдено / что не так со снимком).</summary>
    public string? Message { get; set; }

    /// <summary>Результат нейросети по кадрам (JSON, без картинок — они лежат на диске).</summary>
    public string? ResultJson { get; set; }

    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

    public DateTime? ProcessedAt { get; set; }

    [NotMapped]
    public string Extension
        => $".{Mime.Split('/')[1]}";
}
