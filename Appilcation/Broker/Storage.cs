namespace Broker;

/// <summary>Где лежат загруженные файлы и картинки с рамками от нейросети.</summary>
public static class Storage
{
    public static string PhotosDir
        => Path.Combine(Environment.CurrentDirectory, "static", "photos");

    public static string ResultsDir(Guid fileId)
        => Path.Combine(Environment.CurrentDirectory, "static", "results", fileId.ToString());

    public static string FrameImagePath(Guid fileId, int index)
        => Path.Combine(ResultsDir(fileId), $"{index}.jpg");
}
