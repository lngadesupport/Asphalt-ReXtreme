using System.Text.Json;

namespace ReXtremeSDK.Core;

public static class ContentTemplateService
{
    private static readonly JsonSerializerOptions JsonOptions = new() { WriteIndented = true };

    public static string CreateVehicle(string projectRoot, string id, string name, string category, string baseProfile,
        double speed, double acceleration, double handling, double nitro)
    {
        var vehicle = new RxVehicle
        {
            Id = id,
            Name = name,
            Category = category,
            BaseOriginalProfile = baseProfile,
            PhysicsMode = "clone-profile",
            Performance = new RxPerformanceBars
            {
                Speed = Clamp(speed / 100.0),
                Acceleration = Clamp(acceleration / 100.0),
                Handling = Clamp(handling / 100.0),
                Nitro = Clamp(nitro / 100.0)
            }
        };

        var path = Path.Combine(projectRoot, "content", "vehicles", SafeFileName(id) + ".json");
        ProjectService.SaveJson(path, vehicle);
        return path;
    }

    public static string CreateEvent(string projectRoot, string id, string name, string track, string mode, int laps)
    {
        var data = new
        {
            schema_version = 1,
            id,
            name,
            track,
            mode,
            laps = Math.Max(1, laps),
            allowed_categories = Array.Empty<string>(),
            objectives = Array.Empty<object>(),
            rewards = Array.Empty<object>(),
            music = Array.Empty<string>(),
            hud_layout = (string?)null
        };
        return Write(projectRoot, "content/events", id, data);
    }

    public static string CreateCareerSeason(string projectRoot, string id, string name)
    {
        var data = new
        {
            schema_version = 1,
            id,
            name,
            insert_mode = "new-season",
            target_original_season = (string?)null,
            nodes = Array.Empty<object>(),
            completion_rewards = Array.Empty<object>()
        };
        return Write(projectRoot, "content/career", id, data);
    }

    public static string CreateHudLayout(string projectRoot, string id, string baseHud = "original")
    {
        var data = new
        {
            schema_version = 1,
            id,
            @base = baseHud,
            components = new object[]
            {
                new { id = "speed", type = "original-speedometer", anchor = "bottom-right", x = 0.0, y = 0.0, scale = 1.0, opacity = 1.0, binding = "player.speed" },
                new { id = "nitro", type = "original-nitro", anchor = "bottom-center", x = 0.0, y = 0.0, scale = 1.0, opacity = 1.0, binding = "player.nitro" },
                new { id = "position", type = "original-position", anchor = "top-left", x = 0.0, y = 0.0, scale = 1.0, opacity = 1.0, binding = "race.position" }
            },
            aspect_variants = new { }
        };
        return Write(projectRoot, "content/hud", id, data);
    }

    private static string Write(string root, string folder, string id, object value)
    {
        var dir = Path.Combine(root, folder.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(dir);
        var path = Path.Combine(dir, SafeFileName(id) + ".json");
        File.WriteAllText(path, JsonSerializer.Serialize(value, JsonOptions) + Environment.NewLine);
        return path;
    }

    private static string SafeFileName(string id) =>
        string.Concat(id.Select(c => char.IsLetterOrDigit(c) || c is '.' or '-' or '_' ? c : '_'));

    private static double Clamp(double value) => Math.Max(0, Math.Min(1, value));
}
