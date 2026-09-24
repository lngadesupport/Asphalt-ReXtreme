using System.Text.Json;

namespace ReXtremeSDK.Core;

public static class ContentTemplateService
{
    private static readonly JsonSerializerOptions JsonOptions = new() { WriteIndented = true };

    public static string CreateVehicle(string projectRoot, string id, string name, string archetype,
        string performanceClass, string baseProfile,
        double speed, double acceleration, double handling, double nitro)
    {
        var vehicle = new RxVehicle
        {
            Id = id,
            Name = name,
            Archetype = archetype,
            PerformanceClass = performanceClass,
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
        SaveEvent(projectRoot, id, name, track, mode, laps, null, null);

    public static string SaveEvent(string projectRoot, string id, string name, string track, string mode, int laps,
        string? musicId, string? hudLayout) =>
        Write(projectRoot, "content/events", id, new
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
            music = string.IsNullOrWhiteSpace(musicId) ? Array.Empty<string>() : new[] { musicId.Trim() },
            hud_layout = string.IsNullOrWhiteSpace(hudLayout) ? null : hudLayout.Trim()
        });

    public static string CreateSpecialEvent(string projectRoot, string id, string name) =>
        SaveSpecialEvent(projectRoot, id, name, "permanent", Array.Empty<string>());

    public static string SaveSpecialEvent(string projectRoot, string id, string name, string availability,
        IEnumerable<string> eventIds)
    {
        var stages = eventIds.Where(x => !string.IsNullOrWhiteSpace(x)).Select(x => x.Trim()).ToArray();
        var stageData = stages.Select((eventId, index) => new
        {
            id = $"stage-{index + 1:000}",
            @event = eventId,
            required_previous = index == 0 ? Array.Empty<string>() : new[] { $"stage-{index:000}" }
        }).ToArray();

        return Write(projectRoot, "content/special-events", id, new
        {
            schema_version = 1,
            id,
            name,
            banner = (string?)null,
            availability,
            unlock_requirement = (object?)null,
            stages = stageData,
            completion_rewards = Array.Empty<object>()
        });
    }

    public static string CreateCareerSeason(string projectRoot, string id, string name) =>
        SaveCareerSeason(projectRoot, id, name, "new-season", null, Array.Empty<string>());

    public static string SaveCareerSeason(string projectRoot, string id, string name, string insertMode,
        string? targetOriginalSeason, IEnumerable<string> eventIds)
    {
        var events = eventIds.Where(x => !string.IsNullOrWhiteSpace(x)).Select(x => x.Trim()).ToArray();
        var nodes = events.Select((eventId, index) => new
        {
            id = $"race-{index + 1:000}",
            @event = eventId,
            requires = index == 0 ? Array.Empty<string>() : new[] { $"race-{index:000}" },
            star_gate = (int?)null
        }).ToArray();

        return Write(projectRoot, "content/career", id, new
        {
            schema_version = 1,
            id,
            name,
            insert_mode = insertMode,
            target_original_season = string.IsNullOrWhiteSpace(targetOriginalSeason) ? null : targetOriginalSeason.Trim(),
            nodes,
            completion_rewards = Array.Empty<object>()
        });
    }

    public static string CreateTrack(string projectRoot, string id, string name) =>
        Write(projectRoot, "content/tracks", id, new
        {
            schema_version = 1, id, name, geometry = "assets/models/track.glb", collision = (string?)null,
            start_grid = Array.Empty<object>(), finish = (object?)null, checkpoints = Array.Empty<object>(),
            respawns = Array.Empty<object>(), ai_routes = Array.Empty<object>(), shortcuts = Array.Empty<object>(),
            replay_cameras = Array.Empty<object>(), audio_zones = Array.Empty<object>(), environment = (string?)null
        });

    public static string CreateLivery(string projectRoot, string id, string name, string vehicle) =>
        CreateLivery(projectRoot, id, name, vehicle, "#FFFFFF", null);

    public static string CreateLivery(string projectRoot, string id, string name, string vehicle, string baseColor, string? textureSource) =>
        Write(projectRoot, "content/liveries", id, new
        {
            schema_version = 1,
            id,
            name,
            vehicle,
            layers = string.IsNullOrWhiteSpace(textureSource)
                ? new object[]
                {
                    new { type = "paint", color = baseColor, source = (string?)null, opacity = 1.0, transform = (object?)null }
                }
                : new object[]
                {
                    new { type = "paint", color = baseColor, source = (string?)null, opacity = 1.0, transform = (object?)null },
                    new { type = "texture", color = (string?)null, source = textureSource, opacity = 1.0, transform = (object?)null }
                }
        });

    public static string SaveHudLayout(string projectRoot, string id, IEnumerable<RxHudComponent> components)
    {
        var path = Path.Combine(projectRoot, "content", "hud", SafeFileName(id) + ".json");
        ProjectService.SaveJson(path, new RxHudLayout { Id = id, Base = "original", Components = components.ToList() });
        return path;
    }

    public static string CreateReplayPreset(string projectRoot, string id, string name) =>
        Write(projectRoot, "content/replay", id, new
        {
            schema_version = 1,
            id,
            name,
            timeline = true,
            speed_steps = new[] { 0.10, 0.25, 0.50, 1.0, 2.0, 4.0 },
            frame_step = true,
            event_markers = new[] { "start", "takedown", "jump", "wreck", "overtake", "finish" },
            cameras = new[] { "follow", "chase", "front", "rear", "side", "wheel", "bumper", "hood", "cinematic", "track", "free" },
            allow_target_switch = true,
            hud_toggle = true,
            photo_mode = true
        });

    public static string CreatePhotoPreset(string projectRoot, string id, string name) =>
        Write(projectRoot, "content/photo", id, new
        {
            schema_version = 1,
            id,
            name,
            entry_points = new[] { "pause-menu", "replay-pause" },
            free_camera = true,
            orbit_camera = true,
            fov = 55.0,
            camera_distance = 1.0,
            camera_height = 0.0,
            camera_roll = 0.0,
            hide_hud = true,
            screenshot = true,
            renderer_effects = Array.Empty<string>()
        });

    public static string CreateGraphicsCapabilityPreset(string projectRoot, string id, string name) =>
        Write(projectRoot, "content/graphics", id, new
        {
            schema_version = 1,
            id,
            name,
            capability_source = "original-renderer-audit",
            original_default = true,
            options = Array.Empty<object>(),
            notes = "Only populate options confirmed by Asphalt Xtreme renderer/config/runtime audit."
        });

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
