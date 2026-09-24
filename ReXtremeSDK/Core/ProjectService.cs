using System.Text.Json;
using System.Text.RegularExpressions;

namespace ReXtremeSDK.Core;

public sealed class ProjectService
{
    public static readonly string[] ProjectFolders =
    [
        "assets/source", "assets/models", "assets/textures", "assets/music", "assets/audio", "assets/ui",
        "content/vehicles", "content/tracks", "content/events", "content/special-events",
        "content/career", "content/championships", "content/hud", "content/liveries",
        "content/environment", "content/replay", "content/photo", "content/graphics",
        "scripts", "localization"
    ];

    public static readonly HashSet<string> MusicExtensions =
        new(StringComparer.OrdinalIgnoreCase) { ".wav", ".flac", ".ogg", ".mp3", ".aac", ".m4a" };

    public static readonly HashSet<string> TextureExtensions =
        new(StringComparer.OrdinalIgnoreCase) { ".png", ".jpg", ".jpeg", ".tga", ".dds", ".tif", ".tiff", ".bmp", ".webp", ".exr", ".hdr" };

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        PropertyNamingPolicy = null
    };

    public string? CurrentProjectPath { get; private set; }

    public void CreateProject(string root, string id, string name, string type = "full-expansion")
    {
        Directory.CreateDirectory(root);
        foreach (var folder in ProjectFolders)
            Directory.CreateDirectory(Path.Combine(root, folder.Replace('/', Path.DirectorySeparatorChar)));

        var manifest = new RxManifest { Id = id, Name = name, Type = type };
        SaveJson(Path.Combine(root, "manifest.json"), manifest);
        File.WriteAllText(Path.Combine(root, "README.md"),
            $"# {name}{Environment.NewLine}{Environment.NewLine}" +
            "ReXtreme SDK standalone project. Build output is .rxmod; the game only needs the Mod Runtime." +
            Environment.NewLine);
        CurrentProjectPath = root;
    }

    public void OpenProject(string root)
    {
        if (!File.Exists(Path.Combine(root, "manifest.json")))
            throw new InvalidDataException("A pasta selecionada não contém manifest.json.");
        CurrentProjectPath = root;
    }

    public RxManifest LoadManifest()
    {
        RequireProject();
        return LoadJson<RxManifest>(Path.Combine(CurrentProjectPath!, "manifest.json"));
    }

    public IReadOnlyList<ValidationMessage> Validate()
    {
        RequireProject();
        var root = CurrentProjectPath!;
        var output = new List<ValidationMessage>();
        var manifestPath = Path.Combine(root, "manifest.json");

        RxManifest? manifest = null;
        try { manifest = LoadJson<RxManifest>(manifestPath); }
        catch (Exception ex)
        {
            output.Add(new("ERROR", "manifest.invalid", ex.Message, manifestPath));
            return output;
        }

        if (string.IsNullOrWhiteSpace(manifest.Id) ||
            !Regex.IsMatch(manifest.Id, "^[a-z0-9]+(?:[._-][a-z0-9]+)+$"))
            output.Add(new("ERROR", "manifest.id", "Use um ID namespaced em minúsculas, ex.: com.autor.expansao.", manifestPath));
        if (string.IsNullOrWhiteSpace(manifest.Name))
            output.Add(new("ERROR", "manifest.name", "Nome do projeto é obrigatório.", manifestPath));
        if (manifest.SdkApi < 1)
            output.Add(new("ERROR", "manifest.sdk_api", "sdk_api deve ser >= 1.", manifestPath));

        var dependencyIds = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var dep in manifest.Dependencies)
        {
            if (string.IsNullOrWhiteSpace(dep.Id))
            {
                output.Add(new("ERROR", "manifest.dependency_id", "Dependência sem ID.", manifestPath));
                continue;
            }
            if (dep.Id.Equals(manifest.Id, StringComparison.OrdinalIgnoreCase))
                output.Add(new("ERROR", "manifest.dependency_self", "Um mod não pode depender de si mesmo.", manifestPath));
            if (!dependencyIds.Add(dep.Id))
                output.Add(new("ERROR", "manifest.dependency_duplicate", $"Dependência duplicada: {dep.Id}", manifestPath));
        }

        var ids = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        var contentDir = Path.Combine(root, "content");
        if (Directory.Exists(contentDir))
        {
            foreach (var file in Directory.EnumerateFiles(contentDir, "*.json", SearchOption.AllDirectories))
            {
                try
                {
                    using var doc = JsonDocument.Parse(File.ReadAllText(file));
                    if (doc.RootElement.ValueKind == JsonValueKind.Object &&
                        doc.RootElement.TryGetProperty("id", out var idNode) &&
                        idNode.ValueKind == JsonValueKind.String)
                    {
                        var id = idNode.GetString()!;
                        if (!ids.TryAdd(id, file))
                            output.Add(new("ERROR", "content.duplicate_id", $"ID duplicado: {id}", file));
                    }
                }
                catch (Exception ex)
                {
                    output.Add(new("ERROR", "content.json", ex.Message, file));
                }
            }
        }

        var vehicleRegistry = new OriginalVehicleRegistryService().Load();
        var verifiedProfiles = vehicleRegistry.Profiles.ToDictionary(x => x.Id, StringComparer.OrdinalIgnoreCase);
        var vehicleDir = Path.Combine(root, "content", "vehicles");
        if (Directory.Exists(vehicleDir))
        {
            foreach (var file in Directory.EnumerateFiles(vehicleDir, "*.json"))
            {
                try
                {
                    var v = LoadJson<RxVehicle>(file);
                    if (!OriginalVehicleRegistryService.OfficialArchetypes.Contains(v.Archetype, StringComparer.OrdinalIgnoreCase))
                        output.Add(new("ERROR", "vehicle.archetype", $"Arquétipo original inválido: {v.Archetype}", file));
                    if (!OriginalVehicleRegistryService.PerformanceClasses.Contains(v.PerformanceClass, StringComparer.OrdinalIgnoreCase))
                        output.Add(new("ERROR", "vehicle.performance_class", $"Classe de performance inválida: {v.PerformanceClass}", file));

                    if (string.IsNullOrWhiteSpace(v.BaseOriginalProfile))
                    {
                        output.Add(new("ERROR", "vehicle.base_profile",
                            "Veículos customizados devem referenciar um perfil original extraído e verificado.", file));
                    }
                    else if (!verifiedProfiles.TryGetValue(v.BaseOriginalProfile, out var baseProfile))
                    {
                        output.Add(new("ERROR", "vehicle.base_profile_unknown",
                            $"Perfil original não encontrado no registry verificado: {v.BaseOriginalProfile}", file));
                    }
                    else
                    {
                        if (!baseProfile.Archetype.Equals(v.Archetype, StringComparison.OrdinalIgnoreCase))
                            output.Add(new("ERROR", "vehicle.profile_archetype",
                                $"O perfil {baseProfile.Id} pertence a {baseProfile.Archetype}, não a {v.Archetype}.", file));
                        if (!baseProfile.PerformanceClass.Equals(v.PerformanceClass, StringComparison.OrdinalIgnoreCase))
                            output.Add(new("WARNING", "vehicle.profile_class",
                                $"O perfil base é classe {baseProfile.PerformanceClass}; o conteúdo declara {v.PerformanceClass}.", file));
                    }

                    foreach (var (name, value) in new[]
                    {
                        ("speed", v.Performance.Speed), ("acceleration", v.Performance.Acceleration),
                        ("handling", v.Performance.Handling), ("nitro", v.Performance.Nitro)
                    })
                        if (value is < 0 or > 1)
                            output.Add(new("ERROR", "vehicle.performance", $"{name} deve ficar entre 0 e 1.", file));
                }
                catch (Exception ex)
                {
                    output.Add(new("ERROR", "vehicle.json", ex.Message, file));
                }
            }
        }

        ValidateReplayContent(root, output);
        ValidatePhotoContent(root, output);
        ValidateGraphicsContent(root, output);

        if (output.Count == 0)
            output.Add(new("INFO", "project.valid", "Projeto válido para a fundação atual do ReXtreme SDK.", root));
        return output;
    }

    private static void ValidateReplayContent(string root, List<ValidationMessage> output)
    {
        var dir = Path.Combine(root, "content", "replay");
        if (!Directory.Exists(dir)) return;
        foreach (var file in Directory.EnumerateFiles(dir, "*.json"))
        {
            try
            {
                using var doc = JsonDocument.Parse(File.ReadAllText(file));
                var r = doc.RootElement;
                if (!r.TryGetProperty("id", out _))
                    output.Add(new("ERROR", "replay.id", "Replay preset requer id.", file));
                if (r.TryGetProperty("speed_steps", out var steps) && steps.ValueKind != JsonValueKind.Array)
                    output.Add(new("ERROR", "replay.speed_steps", "speed_steps deve ser um array.", file));
            }
            catch (Exception ex) { output.Add(new("ERROR", "replay.json", ex.Message, file)); }
        }
    }

    private static void ValidatePhotoContent(string root, List<ValidationMessage> output)
    {
        var dir = Path.Combine(root, "content", "photo");
        if (!Directory.Exists(dir)) return;
        foreach (var file in Directory.EnumerateFiles(dir, "*.json"))
        {
            try
            {
                using var doc = JsonDocument.Parse(File.ReadAllText(file));
                var r = doc.RootElement;
                if (!r.TryGetProperty("id", out _))
                    output.Add(new("ERROR", "photo.id", "Photo Mode preset requer id.", file));
                if (r.TryGetProperty("fov", out var fov) && fov.ValueKind == JsonValueKind.Number &&
                    (fov.GetDouble() < 1 || fov.GetDouble() > 179))
                    output.Add(new("ERROR", "photo.fov", "FOV deve ficar entre 1 e 179; o runtime ainda aplicará limites reais da câmera original.", file));
            }
            catch (Exception ex) { output.Add(new("ERROR", "photo.json", ex.Message, file)); }
        }
    }

    private static void ValidateGraphicsContent(string root, List<ValidationMessage> output)
    {
        var dir = Path.Combine(root, "content", "graphics");
        if (!Directory.Exists(dir)) return;
        foreach (var file in Directory.EnumerateFiles(dir, "*.json"))
        {
            try
            {
                using var doc = JsonDocument.Parse(File.ReadAllText(file));
                var r = doc.RootElement;
                if (!r.TryGetProperty("id", out _))
                    output.Add(new("ERROR", "graphics.id", "Graphics preset requer id.", file));
                if (r.TryGetProperty("capability_source", out var source) &&
                    source.ValueKind == JsonValueKind.String &&
                    !string.Equals(source.GetString(), "original-renderer-audit", StringComparison.Ordinal))
                    output.Add(new("ERROR", "graphics.capability_source",
                        "Configurações gráficas devem vir da auditoria real do renderer original.", file));
            }
            catch (Exception ex) { output.Add(new("ERROR", "graphics.json", ex.Message, file)); }
        }
    }

    public void SaveManifest(RxManifest manifest)
    {
        RequireProject();
        SaveJson(Path.Combine(CurrentProjectPath!, "manifest.json"), manifest);
    }

    public void AddDependency(string id, string version)
    {
        var manifest = LoadManifest();
        id = id.Trim();
        version = string.IsNullOrWhiteSpace(version) ? "*" : version.Trim();
        if (string.IsNullOrWhiteSpace(id))
            throw new InvalidDataException("ID da dependência é obrigatório.");
        if (id.Equals(manifest.Id, StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("O projeto não pode depender de si mesmo.");

        manifest.Dependencies.RemoveAll(x => x.Id.Equals(id, StringComparison.OrdinalIgnoreCase));
        manifest.Dependencies.Add(new RxDependency { Id = id, Version = version });
        SaveManifest(manifest);
    }

    public void RemoveDependency(string id)
    {
        var manifest = LoadManifest();
        manifest.Dependencies.RemoveAll(x => x.Id.Equals(id, StringComparison.OrdinalIgnoreCase));
        SaveManifest(manifest);
    }

    public string ImportMusic(string file, string id, string title, string artist, string scope)
    {
        RequireProject();
        var ext = Path.GetExtension(file);
        if (!MusicExtensions.Contains(ext))
            throw new InvalidDataException($"Formato de música ainda não aceito: {ext}");

        var musicDir = Path.Combine(CurrentProjectPath!, "assets", "music");
        Directory.CreateDirectory(musicDir);
        var target = Path.Combine(musicDir, id + ext.ToLowerInvariant());
        File.Copy(file, target, true);

        var catalogPath = Path.Combine(CurrentProjectPath!, "content", "music.json");
        RxMusicCatalog catalog = File.Exists(catalogPath) ? LoadJson<RxMusicCatalog>(catalogPath) : new();
        catalog.Tracks.RemoveAll(x => x.Id.Equals(id, StringComparison.OrdinalIgnoreCase));
        catalog.Tracks.Add(new RxMusicTrack
        {
            Id = id, Title = title, Artist = artist,
            Source = Path.GetRelativePath(CurrentProjectPath!, target).Replace('\', '/'),
            Scope = scope
        });
        SaveJson(catalogPath, catalog);
        return target;
    }

    public string ImportTexture(string file)
    {
        RequireProject();
        var ext = Path.GetExtension(file);
        if (!TextureExtensions.Contains(ext))
            throw new InvalidDataException($"Formato de textura ainda não aceito: {ext}");

        var textureDir = Path.Combine(CurrentProjectPath!, "assets", "textures");
        Directory.CreateDirectory(textureDir);
        var target = Path.Combine(textureDir, Path.GetFileName(file));
        File.Copy(file, target, true);
        return Path.GetRelativePath(CurrentProjectPath!, target).Replace(Path.DirectorySeparatorChar, '/');
    }

    public static T LoadJson<T>(string file) =>
        JsonSerializer.Deserialize<T>(File.ReadAllText(file), JsonOptions)
        ?? throw new InvalidDataException($"JSON vazio ou inválido: {file}");

    public static void SaveJson<T>(string file, T value)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(file)!);
        File.WriteAllText(file, JsonSerializer.Serialize(value, JsonOptions) + Environment.NewLine);
    }

    private void RequireProject()
    {
        if (CurrentProjectPath is null)
            throw new InvalidOperationException("Abra ou crie um projeto primeiro.");
    }
}
