using System.Text.Json;
using System.Text.RegularExpressions;

namespace ReXtremeSDK.Core;

public sealed class OriginalVehicleScanService
{
    private static readonly Regex ElementRegex = new(
        @"<[^>]*k_2206374417=""(?<car_def>[^""]+)""[^>]*>",
        RegexOptions.Compiled | RegexOptions.Singleline);

    private static readonly Regex AttributeRegex = new(
        @"(?<key>k_\d+)=""(?<value>[^""]*)""",
        RegexOptions.Compiled);

    public OriginalVehicleScanReport ScanFile(string sourceFile)
    {
        if (!File.Exists(sourceFile))
            throw new FileNotFoundException("Arquivo de definições original não encontrado.", sourceFile);

        var text = File.ReadAllText(sourceFile, Encoding.UTF8);
        var vehicles = new List<OriginalVehicleScanEntry>();
        var ids = new HashSet<int>();

        foreach (Match element in ElementRegex.Matches(text))
        {
            var attrs = AttributeRegex.Matches(element.Value)
                .Cast<Match>()
                .GroupBy(m => m.Groups["key"].Value)
                .ToDictionary(
                    g => g.Key,
                    g => g.Last().Groups["value"].Value,
                    StringComparer.Ordinal);

            if (!attrs.TryGetValue("k_4250631189", out var carIdText) ||
                !int.TryParse(carIdText, out var carId) ||
                carId <= 0)
                continue;

            if (!ids.Add(carId))
                continue;

            attrs.TryGetValue("k_1571869371", out var performanceClass);
            attrs.TryGetValue("k_1914113855", out var rankText);
            double.TryParse(rankText, System.Globalization.NumberStyles.Float,
                System.Globalization.CultureInfo.InvariantCulture, out var rank);

            vehicles.Add(new OriginalVehicleScanEntry
            {
                CarId = carId,
                CarDef = element.Groups["car_def"].Value,
                PerformanceClass = performanceClass ?? "",
                BaseRank = rank,
                RawAttributes = attrs
            });
        }

        if (vehicles.Count == 0)
            throw new InvalidDataException(
                "Nenhuma definição de veículo compatível foi encontrada. O arquivo precisa conter o banco original com k_2206374417/k_4250631189.");

        return new OriginalVehicleScanReport
        {
            SchemaVersion = 1,
            SourceFile = Path.GetFullPath(sourceFile),
            ScannedAtUtc = DateTime.UtcNow,
            Vehicles = vehicles.OrderBy(v => v.CarId).ToList()
        };
    }

    public string SaveReport(string projectRoot, OriginalVehicleScanReport report)
    {
        var dir = Path.Combine(projectRoot, "research");
        Directory.CreateDirectory(dir);
        var path = Path.Combine(dir, "original_vehicle_scan.json");
        File.WriteAllText(path,
            JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true }) + Environment.NewLine);
        return path;
    }
}

public sealed class OriginalVehicleScanReport
{
    [System.Text.Json.Serialization.JsonPropertyName("schema_version")]
    public int SchemaVersion { get; set; } = 1;

    [System.Text.Json.Serialization.JsonPropertyName("source_file")]
    public string SourceFile { get; set; } = "";

    [System.Text.Json.Serialization.JsonPropertyName("scanned_at_utc")]
    public DateTime ScannedAtUtc { get; set; }

    [System.Text.Json.Serialization.JsonPropertyName("vehicles")]
    public List<OriginalVehicleScanEntry> Vehicles { get; set; } = [];
}

public sealed class OriginalVehicleScanEntry
{
    [System.Text.Json.Serialization.JsonPropertyName("car_id")]
    public int CarId { get; set; }

    [System.Text.Json.Serialization.JsonPropertyName("car_def")]
    public string CarDef { get; set; } = "";

    [System.Text.Json.Serialization.JsonPropertyName("performance_class")]
    public string PerformanceClass { get; set; } = "";

    [System.Text.Json.Serialization.JsonPropertyName("base_rank")]
    public double BaseRank { get; set; }

    [System.Text.Json.Serialization.JsonPropertyName("raw_attributes")]
    public Dictionary<string, string> RawAttributes { get; set; } = [];
}
