using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Broker.Infrastructure.PostgreSQL.Migrations
{
    /// <inheritdoc />
    public partial class AddInspectionResults : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<DateTime>(
                name: "CreatedAt",
                table: "Files",
                type: "timestamp with time zone",
                nullable: false,
                defaultValueSql: "now()");

            migrationBuilder.AddColumn<string>(
                name: "Message",
                table: "Files",
                type: "text",
                nullable: true);

            migrationBuilder.AddColumn<DateTime>(
                name: "ProcessedAt",
                table: "Files",
                type: "timestamp with time zone",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "ResultJson",
                table: "Files",
                type: "text",
                nullable: true);

            // уже загруженные файлы — в очередь (3 = FileStatus.Pending)
            migrationBuilder.AddColumn<int>(
                name: "Status",
                table: "Files",
                type: "integer",
                nullable: false,
                defaultValue: 3);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(name: "CreatedAt", table: "Files");
            migrationBuilder.DropColumn(name: "Message", table: "Files");
            migrationBuilder.DropColumn(name: "ProcessedAt", table: "Files");
            migrationBuilder.DropColumn(name: "ResultJson", table: "Files");
            migrationBuilder.DropColumn(name: "Status", table: "Files");
        }
    }
}
