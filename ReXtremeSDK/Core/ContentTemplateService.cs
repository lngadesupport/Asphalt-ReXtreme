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

    public static string CreateEvent(string projectRoot, string id, string name, string track, string mode, int laps) =>
        Write(projectRoot, "content/events", id, new
        {
            schema_version = 1, id, name, track, mode, laps = Math.Max(1, laps),
            allowed_categories = Array.Empty<string>(), objectives = Array.Empty<object>(),
            rewards = Array.Empty<object>(), music = Array.Empty<string>(), hud_layout = (string?)null
        });

    public static string CreateSpecialEvent(string projectRoot, string id, string name) =>
        Write(projectRoot, "content/special-events", id, new
        {
            schema_version = 1, id, name, banner = (string?)null, availability = "permanent",
            unlock_requirement = (object?)null, stages = Array.Empty<object>(), completion_rewards = Array.Empty<object>()
        });

    public static string CreateCareerSeason(string projectRoot, string id, string name) =>
        Write(projectRoot, "content/career", id, new
        {
            schema_version = 1, id, name, insert_mode = "new-season", target_original_season = (string?)null,
            nodes = Array.Empty<object>(), completion_rewards = Array.Empty<object>()
        });

    public static string CreateTrack(string projectRoot, string id, string name) =>
        Write(projectRoot, "content/tracks", id, new
        {
            schema_version = 1, id, name, geometry = "assets/models/track.glb", collision = (string?)null,
            start_grid = Array.Empty<object>(), finish = (object?)null, checkpoints = Array.Empty<object>(),
            respawns = Array.Empty<object>(), ai_routes = Array.Empty<object>(), shortcuts = Array.Empty<object>(),
            replay_cameras = Array.Empty<object>(), audio_zones = Array.Empty<object>(), environment = (string?)null
        });

    public static string CreateLivery(string projectRoot, string id, string name, string vehicle) =>
        Write(projectRoot, "content/liveries", id, new
        {
            schema_version = 1, id, name, vehicle,
            layers = new object[] { new { type = "paint", source = (string?)null, opacity = 1.0, transform = (object?)null } }
        });

    public static string SaveHudLayout(string projectRoot, string id, IEnumerable<RxHudComponent> components)
    {
        var path = Path.Combine(projectRoot, "content", "hud", SafeFileName(id) + ".json");
        ProjectService.SaveJson(path, new RxHudLayout { Id = id, Base = "original", Components = components.ToList() });
        return path;
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
