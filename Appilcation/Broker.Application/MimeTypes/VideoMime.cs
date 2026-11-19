namespace Broker.Application.MimeTypes
{
    public static class VideoMime
    {
        private static readonly List<string> _mimes = new List<string>();

        public static bool IsValid(string mime)
            => _mimes.Contains(mime);

        static VideoMime()
            => _mimes.AddRange("video/mp4");
    }
}
