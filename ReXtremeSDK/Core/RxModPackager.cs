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
}
