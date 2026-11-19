namespace Broker.Model.Enums
{
    public enum FileStatus
    {
        NotExists,

        Ok,

        HasProblems,

        // ниже — этапы обработки (добавлены в конец, чтобы не сдвинуть значения в БД)
        Pending,

        Processing,

        Failed
    }
}
