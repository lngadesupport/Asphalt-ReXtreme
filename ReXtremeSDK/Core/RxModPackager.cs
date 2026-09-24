using System.IO.Compression;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace ReXtremeSDK.Core;

public sealed class RxModPackager
{
    public string Build(string projectRoot, string outputFile)
    {
        var service = new ProjectService();
        service.OpenProject(projectRoot);
        var errors = service.Validate().Where(x => x.Level == "ERROR").ToArray();
        if (errors.Length > 0)
            throw new InvalidDataException("Falha na validação: " + string.Join("; ", errors.Select(x => x.Message)));

        var files = Directory.EnumerateFiles(projectRoot, "*", SearchOption.AllDirectories)
            .Where(p => !p.EndsWith(".rxmod", StringComparison.OrdinalIgnoreCase))
            .Where(p => !p.Contains($"{Path.DirectorySeparatorChar}.git{Path.DirectorySeparatorChar}"))
            .OrderBy(p => Path.GetRelativePath(projectRoot, p), StringComparer.Ordinal)
            .ToArray();

        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outputFile))!);
        if (File.Exists(outputFile)) File.Delete(outputFile);

        var index = new List<object>();
        using var fs = File.Create(outputFile);
        using var zip = new ZipArchive(fs, ZipArchiveMode.Create);
        foreach (var file in files)
        {
            var rel = Path.GetRelativePath(projectRoot, file).Replace('\\', '/');
            var bytes = File.ReadAllBytes(file);
            index.Add(new
            {
                path = rel,
                size = bytes.LongLength,
                sha256 = Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant()
            });

            var entry = zip.CreateEntry(rel, CompressionLevel.Optimal);
            entry.LastWriteTime = new DateTimeOffset(2020, 1, 1, 0, 0, 0, TimeSpan.Zero);
            using var stream = entry.Open();
            stream.Write(bytes);
        }

        var idx = zip.CreateEntry("_rextreme/package-index.json", CompressionLevel.Optimal);
        idx.LastWriteTime = new DateTimeOffset(2020, 1, 1, 0, 0, 0, TimeSpan.Zero);
        using (var writer = new StreamWriter(idx.Open(), new UTF8Encoding(false)))
            writer.Write(JsonSerializer.Serialize(new { format = "rxmod", format_version = 1, files = index },
                new JsonSerializerOptions { WriteIndented = true }));

        return outputFile;
    }

    public IReadOnlyList<ValidationMessage> Verify(string packageFile)
    {
        var result = new List<ValidationMessage>();
        if (!File.Exists(packageFile))
            return [new ValidationMessage("ERROR", "package.missing", "Arquivo .rxmod não encontrado.", packageFile)];

        try
        {
            using var zip = ZipFile.OpenRead(packageFile);

            var duplicate = zip.Entries
                .GroupBy(e => e.FullName, StringComparer.OrdinalIgnoreCase)
                .FirstOrDefault(g => g.Count() > 1);
            if (duplicate is not null)
                result.Add(new("ERROR", "package.duplicate_entry", $"Entrada duplicada no ZIP: {duplicate.Key}", packageFile));

            var indexEntry = zip.GetEntry("_rextreme/package-index.json");
            if (indexEntry is null)
            {
                result.Add(new("ERROR", "package.index_missing", "Índice _rextreme/package-index.json não encontrado.", packageFile));
                return result;
            }

            using var indexStream = indexEntry.Open();
            using var doc = JsonDocument.Parse(indexStream);
            var root = doc.RootElement;
            if (!root.TryGetProperty("format", out var format) || format.GetString() != "rxmod")
                result.Add(new("ERROR", "package.format", "Formato de pacote inválido.", packageFile));

            if (!root.TryGetProperty("files", out var files) || files.ValueKind != JsonValueKind.Array)
            {
                result.Add(new("ERROR", "package.index_invalid", "Índice não possui lista de arquivos.", packageFile));
                return result;
            }

            var indexed = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            foreach (var item in files.EnumerateArray())
            {
                var path = item.GetProperty("path").GetString() ?? "";
                var expectedSize = item.GetProperty("size").GetInt64();
                var expectedHash = item.GetProperty("sha256").GetString() ?? "";
                indexed.Add(path);

                var entry = zip.GetEntry(path);
                if (entry is null)
                {
                    result.Add(new("ERROR", "package.file_missing", $"Arquivo ausente: {path}", packageFile));
                    continue;
                }
                if (entry.Length != expectedSize)
                    result.Add(new("ERROR", "package.size", $"Tamanho divergente: {path}", packageFile));

                using var stream = entry.Open();
                using var sha = SHA256.Create();
                var actual = Convert.ToHexString(sha.ComputeHash(stream)).ToLowerInvariant();
                if (!actual.Equals(expectedHash, StringComparison.OrdinalIgnoreCase))
                    result.Add(new("ERROR", "package.sha256", $"SHA-256 divergente: {path}", packageFile));
            }

            foreach (var entry in zip.Entries)
            {
                if (entry.FullName == "_rextreme/package-index.json") continue;
                if (!indexed.Contains(entry.FullName))
                    result.Add(new("WARNING", "package.unindexed", $"Entrada não indexada: {entry.FullName}", packageFile));
            }

            if (!result.Any(x => x.Level == "ERROR"))
                result.Add(new("INFO", "package.valid", "Pacote .rxmod íntegro.", packageFile));
        }
        catch (Exception ex)
        {
            result.Add(new("ERROR", "package.invalid", ex.Message, packageFile));
        }
        return result;
    }
}
