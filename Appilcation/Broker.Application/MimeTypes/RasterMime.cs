using System.Diagnostics.Contracts;

namespace Broker.Application.MimeTypes
{
    public static class RasterMime
    {
        private static readonly List<string> _mimes = new List<string>();

        public static bool IsValid(string mime)
            => _mimes.Contains(mime);

        static RasterMime()
            => _mimes.AddRange("image/png", "image/jpeg", "image/gif");
    }
}
