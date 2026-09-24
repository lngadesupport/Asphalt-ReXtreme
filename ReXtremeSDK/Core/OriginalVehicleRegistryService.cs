using System.Text.Json;
using System.Text.Json.Serialization;

namespace ReXtremeSDK.Core;

public sealed class OriginalVehicleRegistry
{
    [JsonPropertyName("schema_version")] public int SchemaVersion { get; set; } = 1;
    [JsonPropertyName("archetypes")] public List<OriginalVehicleArchetype> Archetypes { get; set; } = [];
    [JsonPropertyName("profiles")] public List<OriginalVehicleProfile> Profiles { get; set; } = [];
}

public sealed class OriginalVehicleArchetype
{
    [JsonPropertyName("id")] public string Id { get; set; } = "";
    [JsonPropertyName("display_name")] public string DisplayName { get; set; } = "";
}

public sealed class OriginalVehicleProfile
{
    [JsonPropertyName("id")] public string Id { get; set; } = "";
    [JsonPropertyName("car_id")] public int CarId { get; set; }
    [JsonPropertyName("car_def")] public string CarDef { get; set; } = "";
    [JsonPropertyName("display_name")] public string DisplayName { get; set; } = "";
    [JsonPropertyName("archetype")] public string Archetype { get; set; } = "";
    [JsonPropertyName("performance_class")] public string PerformanceClass { get; set; } = "";
    [JsonPropertyName("base_rank")] public double BaseRank { get; set; }
    [JsonPropertyName("performance_bars")] public RxPerformanceBars? PerformanceBars { get; set; }
    [JsonPropertyName("physics")] public Dictionary<string, double> Physics { get; set; } = [];
    [JsonPropertyName("source_verified")] public bool SourceVerified { get; set; }
}

public sealed class OriginalVehicleRegistryService
{
    public static readonly string[] OfficialArchetypes =
    [
        "buggy", "rally-car", "suv", "muscle-car", "pickup", "truck", "monster-truck"
    ];

    public static readonly string[] PerformanceClasses = ["D", "C", "B", "A", "S"];

    public static string UserRegistryPath =>
        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "ReXtremeSDK", "Data", "original_vehicle_registry.json");

    public OriginalVehicleRegistry Load()
    {
        var candidates = new[]
        {
            UserRegistryPath,
            Path.Combine(AppContext.BaseDirectory, "Data", "original_vehicle_registry.json"),
            Path.Combine(AppContext.BaseDirectory, "original_vehicle_registry.json")
        };

        foreach (var path in candidates)
        {
            if (!File.Exists(path)) continue;
            var registry = JsonSerializer.Deserialize<OriginalVehicleRegistry>(
                File.ReadAllText(path),
                new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
            if (registry is not null) return Normalize(registry);
        }

        return Normalize(new OriginalVehicleRegistry());
    }

    public OriginalVehicleRegistry ImportVerified(string sourceFile)
    {
        if (!File.Exists(sourceFile))
            throw new FileNotFoundException("Registry não encontrado.", sourceFile);

        var registry = JsonSerializer.Deserialize<OriginalVehicleRegistry>(
            File.ReadAllText(sourceFile),
            new JsonSerializerOptions { PropertyNameCaseInsensitive = true })
            ?? throw new InvalidDataException("Registry JSON vazio ou inválido.");

        ValidateStrict(registry);

        var normalized = Normalize(registry);
        Directory.CreateDirectory(Path.GetDirectoryName(UserRegistryPath)!);
        File.WriteAllText(UserRegistryPath,
            JsonSerializer.Serialize(normalized, new JsonSerializerOptions { WriteIndented = true }) + Environment.NewLine);
        return normalized;
    }

    public static void ValidateStrict(OriginalVehicleRegistry registry)
    {
        if (registry.SchemaVersion != 1)
            throw new InvalidDataException($"Registry schema_version não suportado: {registry.SchemaVersion}");

        var ids = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var carIds = new HashSet<int>();

        foreach (var p in registry.Profiles)
        {
            if (!p.SourceVerified)
                throw new InvalidDataException($"Perfil {p.Id} não está marcado como source_verified.");
            if (string.IsNullOrWhiteSpace(p.Id) || !ids.Add(p.Id))
                throw new InvalidDataException($"ID de perfil vazio ou duplicado: {p.Id}");
            if (p.CarId <= 0 || !carIds.Add(p.CarId))
                throw new InvalidDataException($"car_id inválido ou duplicado no registry: {p.CarId}");
            if (!OfficialArchetypes.Contains(p.Archetype, StringComparer.OrdinalIgnoreCase))
                throw new InvalidDataException($"Arquétipo não original em {p.Id}: {p.Archetype}");
            if (!PerformanceClasses.Contains(p.PerformanceClass, StringComparer.OrdinalIgnoreCase))
                throw new InvalidDataException($"Classe inválida em {p.Id}: {p.PerformanceClass}");
            if (p.PerformanceBars is not null)
            {
                foreach (var (name, value) in new[]
                {
                    ("speed", p.PerformanceBars.Speed),
                    ("acceleration", p.PerformanceBars.Acceleration),
                    ("handling", p.PerformanceBars.Handling),
                    ("nitro", p.PerformanceBars.Nitro)
                })
                    if (value is < 0 or > 1)
                        throw new InvalidDataException($"{p.Id}: barra {name} fora da faixa 0..1.");
            }
        }
    }

    public static OriginalVehicleRegistry Normalize(OriginalVehicleRegistry registry)
    {
        var known = registry.Archetypes
            .Where(x => !string.IsNullOrWhiteSpace(x.Id))
            .ToDictionary(x => x.Id, StringComparer.OrdinalIgnoreCase);

        foreach (var id in OfficialArchetypes)
        {
            if (known.ContainsKey(id)) continue;
            registry.Archetypes.Add(new OriginalVehicleArchetype
            {
                Id = id,
                DisplayName = DisplayName(id)
            });
        }

        registry.Archetypes = registry.Archetypes
            .Where(x => OfficialArchetypes.Contains(x.Id, StringComparer.OrdinalIgnoreCase))
            .OrderBy(x => Array.FindIndex(OfficialArchetypes, id => id.Equals(x.Id, StringComparison.OrdinalIgnoreCase)))
            .ToList();

        registry.Profiles = registry.Profiles
            .Where(p => p.SourceVerified)
            .Where(p => OfficialArchetypes.Contains(p.Archetype, StringComparer.OrdinalIgnoreCase))
            .Where(p => PerformanceClasses.Contains(p.PerformanceClass, StringComparer.OrdinalIgnoreCase))
            .OrderBy(p => p.Archetype)
            .ThenBy(p => p.BaseRank)
            .ToList();

        return registry;
    }

    public static string DisplayName(string id) => id switch
    {
        "buggy" => "Buggy",
        "rally-car" => "Rally Car",
        "suv" => "SUV",
        "muscle-car" => "Muscle Car",
        "pickup" => "Pickup",
        "truck" => "Truck",
        "monster-truck" => "Monster Truck",
        _ => id
    };
}
