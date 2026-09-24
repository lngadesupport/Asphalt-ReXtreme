using System.Text.Json.Serialization;

namespace ReXtremeSDK.Core;

public sealed class RxManifest
{
    [JsonPropertyName("schema_version")] public int SchemaVersion { get; set; } = 1;
    [JsonPropertyName("id")] public string Id { get; set; } = "";
    [JsonPropertyName("name")] public string Name { get; set; } = "";
    [JsonPropertyName("version")] public string Version { get; set; } = "0.1.0";
    [JsonPropertyName("sdk_api")] public int SdkApi { get; set; } = 1;
    [JsonPropertyName("type")] public string Type { get; set; } = "full-expansion";
    [JsonPropertyName("dependencies")] public List<RxDependency> Dependencies { get; set; } = [];
}

public sealed class RxDependency
{
    [JsonPropertyName("id")] public string Id { get; set; } = "";
    [JsonPropertyName("version")] public string Version { get; set; } = "*";
}

public sealed class RxVehicle
{
    [JsonPropertyName("id")] public string Id { get; set; } = "";
    [JsonPropertyName("name")] public string Name { get; set; } = "";
    [JsonPropertyName("category")] public string Category { get; set; } = "rally";
    [JsonPropertyName("base_original_profile")] public string BaseOriginalProfile { get; set; } = "";
    [JsonPropertyName("physics_mode")] public string PhysicsMode { get; set; } = "clone-profile";
    [JsonPropertyName("performance_bars")] public RxPerformanceBars Performance { get; set; } = new();
    [JsonPropertyName("model")] public string? Model { get; set; }
}

public sealed class RxPerformanceBars
{
    [JsonPropertyName("speed")] public double Speed { get; set; } = .5;
    [JsonPropertyName("acceleration")] public double Acceleration { get; set; } = .5;
    [JsonPropertyName("handling")] public double Handling { get; set; } = .5;
    [JsonPropertyName("nitro")] public double Nitro { get; set; } = .5;
}

public sealed class RxMusicTrack
{
    [JsonPropertyName("id")] public string Id { get; set; } = "";
    [JsonPropertyName("title")] public string Title { get; set; } = "";
    [JsonPropertyName("artist")] public string Artist { get; set; } = "";
    [JsonPropertyName("source")] public string Source { get; set; } = "";
    [JsonPropertyName("scope")] public string Scope { get; set; } = "race";
    [JsonPropertyName("loop")] public bool Loop { get; set; }
}

public sealed class RxMusicCatalog
{
    [JsonPropertyName("schema_version")] public int SchemaVersion { get; set; } = 1;
    [JsonPropertyName("tracks")] public List<RxMusicTrack> Tracks { get; set; } = [];
}

public sealed record ValidationMessage(string Level, string Code, string Message, string? Path = null);
