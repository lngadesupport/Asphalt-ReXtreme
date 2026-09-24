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

    public OriginalVehicleRegistry Load()
    {
        var candidates = new[]
        {
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
