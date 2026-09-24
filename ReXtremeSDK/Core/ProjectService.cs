using System.Text.Json;
using System.Text.RegularExpressions;

namespace ReXtremeSDK.Core;

public sealed class ProjectService
{
    public static readonly string[] ProjectFolders =
    [
        "assets/models", "assets/textures", "assets/music", "assets/audio", "assets/ui",
        "content/vehicles", "content/tracks", "content/events", "content/special-events",
        "content/career", "content/championships", "content/hud", "content/liveries",
        "content/environment", "scripts", "localization"
    ];

    public static readonly string[] VehicleCategories =
    [
        "rally", "monster-truck", "buggy", "suv", "truck", "muscle", "pickup", "other-original-category"
    ];

    public static readonly HashSet<string> MusicExtensions =
        new(StringComparer.OrdinalIgnoreCase) { ".wav", ".flac", ".ogg", ".mp3", ".aac", ".m4a" };

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
        File.WriteAllText(Path.Combine(root, "README.md"), $"# {name}{Environment.NewLine}{Environment.NewLine}ReXtreme SDK project.{Environment.NewLine}");
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

        var vehicleDir = Path.Combine(root, "content", "vehicles");
        if (Directory.Exists(vehicleDir))
        {
            foreach (var file in Directory.EnumerateFiles(vehicleDir, "*.json"))
            {
                try
                {
                    var v = LoadJson<RxVehicle>(file);
                    if (!VehicleCategories.Contains(v.Category))
                        output.Add(new("ERROR", "vehicle.category", $"Categoria não mapeada: {v.Category}", file));
                    if (string.IsNullOrWhiteSpace(v.BaseOriginalProfile))
                        output.Add(new("ERROR", "vehicle.base_profile",
                            "Veículos customizados devem referenciar um perfil original extraído do Asphalt Xtreme.", file));
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

        if (output.Count == 0)
            output.Add(new("INFO", "project.valid", "Projeto válido para a fundação atual do ReXtreme SDK.", root));
        return output;
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
            Source = Path.GetRelativePath(CurrentProjectPath!, target).Replace('\\', '/'),
            Scope = scope
        });
        SaveJson(catalogPath, catalog);
        return target;
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
