using System.Text.Json;

namespace ReXtremeSDK.Core;

public sealed class TrackBundleImporterService
{
    public string Import(string projectRoot, string metadataFile, string trackId, string trackName)
    {
        using var doc = JsonDocument.Parse(File.ReadAllText(metadataFile));
        var root = doc.RootElement;

        if (!root.TryGetProperty("objects", out var objects) || objects.ValueKind != JsonValueKind.Array)
            throw new InvalidDataException("Bundle Blender não contém objects[].");

        var glbName = root.TryGetProperty("glb", out var glbNode) && glbNode.ValueKind == JsonValueKind.String
            ? glbNode.GetString()
            : Path.GetFileNameWithoutExtension(metadataFile.Replace(".rxscene", "", StringComparison.OrdinalIgnoreCase)) + ".glb";
        if (string.IsNullOrWhiteSpace(glbName))
            throw new InvalidDataException("Bundle não informa o GLB.");

        var sourceDir = Path.GetDirectoryName(Path.GetFullPath(metadataFile))!;
        var sourceGlb = Path.Combine(sourceDir, glbName);
        if (!File.Exists(sourceGlb))
            throw new FileNotFoundException("GLB irmão do .rxscene.json não encontrado.", sourceGlb);

        var safe = SafeName(trackId);
        var modelDir = Path.Combine(projectRoot, "assets", "models", "tracks");
        var sourceAssetDir = Path.Combine(projectRoot, "assets", "source", "tracks");
        Directory.CreateDirectory(modelDir);
        Directory.CreateDirectory(sourceAssetDir);

        var targetGlb = Path.Combine(modelDir, safe + ".glb");
        var targetMeta = Path.Combine(sourceAssetDir, safe + ".rxscene.json");
        File.Copy(sourceGlb, targetGlb, true);
        File.Copy(metadataFile, targetMeta, true);

        var starts = new List<object>();
        object? finish = null;
        var checkpoints = new List<object>();
        var respawns = new List<object>();
        var aiRoutes = new List<object>();
        var replayCameras = new List<object>();
        var audioZones = new List<object>();
        var collisions = new List<object>();
        var props = new List<object>();

        foreach (var item in objects.EnumerateArray())
        {
            if (!item.TryGetProperty("rextreme", out var rx) || rx.ValueKind != JsonValueKind.Object)
                continue;
            if (!rx.TryGetProperty("rx_role", out var roleNode) || roleNode.ValueKind != JsonValueKind.String)
                continue;

            var role = roleNode.GetString() ?? "";
            var marker = ToMarker(item, rx);

            switch (role)
            {
                case "start": starts.Add(marker); break;
                case "finish": finish ??= marker; break;
                case "checkpoint": checkpoints.Add(marker); break;
                case "respawn": respawns.Add(marker); break;
                case "ai_route": aiRoutes.Add(marker); break;
                case "replay_camera": replayCameras.Add(marker); break;
                case "audio_zone": audioZones.Add(marker); break;
                case "collision": collisions.Add(marker); break;
                case "prop": props.Add(marker); break;
            }
        }

        if (starts.Count == 0)
            throw new InvalidDataException("Pista sem marker rx_role=start.");
        if (finish is null)
            throw new InvalidDataException("Pista sem marker rx_role=finish.");
        if (checkpoints.Count == 0)
            throw new InvalidDataException("Pista sem checkpoints.");
        if (aiRoutes.Count == 0)
            throw new InvalidDataException("Pista sem ai_route.");

        var track = new
        {
            schema_version = 1,
            id = trackId,
            name = trackName,
            geometry = Path.GetRelativePath(projectRoot, targetGlb).Replace('\\', '/'),
            source_bundle = Path.GetRelativePath(projectRoot, targetMeta).Replace('\\', '/'),
            collision = collisions.Count == 0 ? null : "embedded/marked-in-source-bundle",
            collision_markers = collisions,
            start_grid = starts,
            finish,
            checkpoints,
            respawns,
            ai_routes = aiRoutes,
            shortcuts = Array.Empty<object>(),
            replay_cameras = replayCameras,
            audio_zones = audioZones,
            props,
            environment = (string?)null
        };

        var output = Path.Combine(projectRoot, "content", "tracks", safe + ".json");
        ProjectService.SaveJson(output, track);
        return output;
    }

    private static object ToMarker(JsonElement item, JsonElement rx)
    {
        var name = item.TryGetProperty("name", out var n) ? n.GetString() ?? "" : "";
        var markerId = rx.TryGetProperty("rx_id", out var id) && id.ValueKind == JsonValueKind.String
            ? id.GetString()
            : null;

        return new
        {
            id = string.IsNullOrWhiteSpace(markerId) ? name : markerId,
            source_object = name,
            position = Vector(item, "location"),
            rotation = Vector(item, "rotation_euler"),
            scale = Vector(item, "scale")
        };
    }

    private static double[] Vector(JsonElement item, string property)
    {
        if (!item.TryGetProperty(property, out var v) || v.ValueKind != JsonValueKind.Array)
            return [0, 0, 0];
        return v.EnumerateArray()
            .Take(3)
            .Select(x => x.ValueKind == JsonValueKind.Number ? x.GetDouble() : 0)
            .Concat(new[] { 0.0, 0.0, 0.0 })
            .Take(3)
            .ToArray();
    }

    private static string SafeName(string value) =>
        string.Concat(value.Select(c => char.IsLetterOrDigit(c) || c is '.' or '-' or '_' ? c : '_'));
}
