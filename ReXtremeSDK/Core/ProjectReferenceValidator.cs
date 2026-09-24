using System.Text.Json;

namespace ReXtremeSDK.Core;

public static class ProjectReferenceValidator
{
    public static void Validate(string root, List<ValidationMessage> output)
    {
        var ids = CollectContentIds(root);
        var musicIds = CollectMusicIds(root);
        foreach (var id in musicIds) ids.Add(id);

        ValidateEvents(root, ids, output);
        ValidateSpecialEvents(root, ids, output);
        ValidateCareer(root, ids, output);
        ValidateAssetReferences(root, output);
    }

    private static HashSet<string> CollectContentIds(string root)
    {
        var ids = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var content = Path.Combine(root, "content");
        if (!Directory.Exists(content)) return ids;

        foreach (var file in Directory.EnumerateFiles(content, "*.json", SearchOption.AllDirectories))
        {
            try
            {
                using var doc = JsonDocument.Parse(File.ReadAllText(file));
                if (doc.RootElement.ValueKind == JsonValueKind.Object &&
                    doc.RootElement.TryGetProperty("id", out var id) &&
                    id.ValueKind == JsonValueKind.String &&
                    !string.IsNullOrWhiteSpace(id.GetString()))
                    ids.Add(id.GetString()!);
            }
            catch { }
        }
        return ids;
    }

    private static HashSet<string> CollectMusicIds(string root)
    {
        var ids = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var file = Path.Combine(root, "content", "music.json");
        if (!File.Exists(file)) return ids;
        try
        {
            using var doc = JsonDocument.Parse(File.ReadAllText(file));
            if (!doc.RootElement.TryGetProperty("tracks", out var tracks) || tracks.ValueKind != JsonValueKind.Array)
                return ids;
            foreach (var track in tracks.EnumerateArray())
                if (track.TryGetProperty("id", out var id) && id.ValueKind == JsonValueKind.String)
                    ids.Add(id.GetString() ?? "");
        }
        catch { }
        return ids;
    }

    private static void ValidateEvents(string root, HashSet<string> ids, List<ValidationMessage> output)
    {
        var dir = Path.Combine(root, "content", "events");
        if (!Directory.Exists(dir)) return;

        foreach (var file in Directory.EnumerateFiles(dir, "*.json"))
        {
            using var doc = SafeParse(file, output);
            if (doc is null) continue;
            var e = doc.RootElement;

            CheckContentRef(e, "track", ids, file, "event.track", output);
            CheckContentRef(e, "hud_layout", ids, file, "event.hud", output);

            if (e.TryGetProperty("music", out var music) && music.ValueKind == JsonValueKind.Array)
                foreach (var item in music.EnumerateArray())
                    if (item.ValueKind == JsonValueKind.String)
                        CheckRef(item.GetString(), ids, file, "event.music", output);
        }
    }

    private static void ValidateSpecialEvents(string root, HashSet<string> ids, List<ValidationMessage> output)
    {
        var dir = Path.Combine(root, "content", "special-events");
        if (!Directory.Exists(dir)) return;

        foreach (var file in Directory.EnumerateFiles(dir, "*.json"))
        {
            using var doc = SafeParse(file, output);
            if (doc is null) continue;
            if (!doc.RootElement.TryGetProperty("stages", out var stages) || stages.ValueKind != JsonValueKind.Array)
                continue;

            foreach (var stage in stages.EnumerateArray())
                CheckContentRef(stage, "event", ids, file, "special-event.stage", output);
        }
    }

    private static void ValidateCareer(string root, HashSet<string> ids, List<ValidationMessage> output)
    {
        var dir = Path.Combine(root, "content", "career");
        if (!Directory.Exists(dir)) return;

        foreach (var file in Directory.EnumerateFiles(dir, "*.json"))
        {
            using var doc = SafeParse(file, output);
            if (doc is null) continue;
            if (!doc.RootElement.TryGetProperty("nodes", out var nodes) || nodes.ValueKind != JsonValueKind.Array)
                continue;

            foreach (var node in nodes.EnumerateArray())
                CheckContentRef(node, "event", ids, file, "career.event", output);
        }
    }

    private static void ValidateAssetReferences(string root, List<ValidationMessage> output)
    {
        var content = Path.Combine(root, "content");
        if (!Directory.Exists(content)) return;

        foreach (var file in Directory.EnumerateFiles(content, "*.json", SearchOption.AllDirectories))
        {
            using var doc = SafeParse(file, output);
            if (doc is null) continue;
            Walk(doc.RootElement, file);
        }

        void Walk(JsonElement element, string sourceFile)
        {
            if (element.ValueKind == JsonValueKind.Object)
            {
                foreach (var prop in element.EnumerateObject())
                {
                    if (prop.Value.ValueKind == JsonValueKind.String)
                    {
                        var value = prop.Value.GetString() ?? "";
                        if (LooksLikeProjectAsset(value) && !value.StartsWith("embedded/", StringComparison.OrdinalIgnoreCase))
                        {
                            var absolute = Path.GetFullPath(Path.Combine(root, value.Replace('/', Path.DirectorySeparatorChar)));
                            var project = Path.GetFullPath(root) + Path.DirectorySeparatorChar;
                            if (!absolute.StartsWith(project, StringComparison.OrdinalIgnoreCase))
                                output.Add(new("ERROR", "asset.path_escape", $"Asset sai da pasta do projeto: {value}", sourceFile));
                            else if (!File.Exists(absolute))
                                output.Add(new("ERROR", "asset.missing", $"Asset não encontrado: {value}", sourceFile));
                        }
                    }
                    Walk(prop.Value, sourceFile);
                }
            }
            else if (element.ValueKind == JsonValueKind.Array)
            {
                foreach (var child in element.EnumerateArray()) Walk(child, sourceFile);
            }
        }
    }

    private static bool LooksLikeProjectAsset(string value) =>
        value.StartsWith("assets/", StringComparison.OrdinalIgnoreCase) ||
        value.StartsWith("assets\\", StringComparison.OrdinalIgnoreCase);

    private static void CheckContentRef(JsonElement obj, string property, HashSet<string> ids, string file,
        string code, List<ValidationMessage> output)
    {
        if (!obj.TryGetProperty(property, out var value) || value.ValueKind == JsonValueKind.Null)
            return;
        if (value.ValueKind == JsonValueKind.String)
            CheckRef(value.GetString(), ids, file, code, output);
    }

    private static void CheckRef(string? value, HashSet<string> ids, string file, string code,
        List<ValidationMessage> output)
    {
        if (string.IsNullOrWhiteSpace(value)) return;
        if (value.StartsWith("original.", StringComparison.OrdinalIgnoreCase)) return;
        if (!ids.Contains(value))
            output.Add(new("WARNING", code, $"Referência não resolvida neste projeto: {value}. Pode exigir outro mod/dependência.", file));
    }

    private static JsonDocument? SafeParse(string file, List<ValidationMessage> output)
    {
        try { return JsonDocument.Parse(File.ReadAllText(file)); }
        catch (Exception ex)
        {
            output.Add(new("ERROR", "reference.json", ex.Message, file));
            return null;
        }
    }
}
