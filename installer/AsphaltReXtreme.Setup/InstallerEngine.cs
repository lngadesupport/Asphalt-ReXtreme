using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;
using System.Text.Json;
using Windows.Management.Deployment;

namespace AsphaltReXtreme.Setup;

public sealed class InstallerEngine
{
    public sealed record InstallManifest(
        string product,
        string version,
        string package,
        string certificate,
        string? dependency,
        string? packageSha256,
        string? certificateSha256);

    public sealed record ProgressInfo(double Value, string Status, string Detail);

    private readonly string _payloadDirectory = Path.Combine(AppContext.BaseDirectory, "payload");

    public async Task InstallAsync(IProgress<ProgressInfo> progress, CancellationToken ct = default)
    {
        progress.Report(new(0.04, "Verificando arquivos...", "Validando o payload do ReXtreme."));

        var manifestPath = Path.Combine(_payloadDirectory, "install-manifest.json");
        if (!File.Exists(manifestPath))
            throw new FileNotFoundException("install-manifest.json não foi encontrado.", manifestPath);

        var json = await File.ReadAllTextAsync(manifestPath, ct);
        var manifest = JsonSerializer.Deserialize<InstallManifest>(
            json,
            new JsonSerializerOptions { PropertyNameCaseInsensitive = true })
            ?? throw new InvalidDataException("Manifesto de instalação inválido.");

        var packagePath = RequirePayload(manifest.package);
        var certPath = RequirePayload(manifest.certificate);
        var dependencyPath = string.IsNullOrWhiteSpace(manifest.dependency)
            ? null
            : RequirePayload(manifest.dependency);

        await VerifyHashIfPresentAsync(packagePath, manifest.packageSha256, ct);
        await VerifyHashIfPresentAsync(certPath, manifest.certificateSha256, ct);

        progress.Report(new(0.16, "Preparando o Windows...", "Confiando no certificado local do ReXtreme."));
        TrustPublisherCertificate(certPath);

        progress.Report(new(
            0.28,
            "Preparando dependências...",
            dependencyPath is null
                ? "A dependência VC120 deve já estar instalada."
                : "VC120 x86 será instalada junto com o jogo."));

        var packageUri = new Uri(packagePath, UriKind.Absolute);
        var dependencies = dependencyPath is null
            ? Array.Empty<Uri>()
            : new[] { new Uri(dependencyPath, UriKind.Absolute) };

        var packageManager = new PackageManager();
        var operation = packageManager.AddPackageAsync(
            packageUri,
            dependencies,
            DeploymentOptions.ForceApplicationShutdown);

        operation.Progress = (_, deploymentProgress) =>
        {
            var fraction = deploymentProgress.percentage / 100.0;
            progress.Report(new(
                0.32 + fraction * 0.58,
                "Instalando Asphalt ReXtreme...",
                "Aplicando o Full Repack e registrando a identidade ReXtreme."));
        };

        using var registration = ct.Register(() => operation.Cancel());
        var result = await operation;

        if (result.ExtendedErrorCode is not null)
        {
            throw new InvalidOperationException(
                string.IsNullOrWhiteSpace(result.ErrorText)
                    ? result.ExtendedErrorCode.Message
                    : result.ErrorText,
                result.ExtendedErrorCode);
        }

        progress.Report(new(0.94, "Verificando instalação...", "Confirmando a identidade ReXtreme."));
        var installed = packageManager
            .FindPackagesForUser(string.Empty)
            .FirstOrDefault(p => string.Equals(
                p.Id.Name,
                "ReXtreme.AsphaltXtreme",
                StringComparison.OrdinalIgnoreCase));

        if (installed is null)
            throw new InvalidOperationException("O pacote ReXtreme não foi localizado após a instalação.");

        progress.Report(new(1.0, "Instalação concluída.", "Asphalt ReXtreme está pronto para jogar."));
    }

    public async Task LaunchAsync()
    {
        var packageManager = new PackageManager();
        var package = packageManager
            .FindPackagesForUser(string.Empty)
            .FirstOrDefault(p => string.Equals(
                p.Id.Name,
                "ReXtreme.AsphaltXtreme",
                StringComparison.OrdinalIgnoreCase))
            ?? throw new InvalidOperationException("Asphalt ReXtreme não está instalado.");

        var entries = await package.GetAppListEntriesAsync();
        var entry = entries.FirstOrDefault()
            ?? throw new InvalidOperationException("O pacote não expõe uma entrada inicializável.");

        if (!await entry.LaunchAsync())
            throw new InvalidOperationException("O Windows recusou a inicialização do jogo.");
    }

    private string RequirePayload(string fileName)
    {
        var path = Path.GetFullPath(Path.Combine(_payloadDirectory, fileName));
        var root = Path.GetFullPath(_payloadDirectory) + Path.DirectorySeparatorChar;

        if (!path.StartsWith(root, StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("O manifesto de instalação contém um caminho inválido.");

        if (!File.Exists(path))
            throw new FileNotFoundException($"Arquivo obrigatório ausente: {fileName}", path);

        return path;
    }

    private static void TrustPublisherCertificate(string path)
    {
        using var cert = new X509Certificate2(path);
        using var store = new X509Store(StoreName.TrustedPeople, StoreLocation.LocalMachine);
        store.Open(OpenFlags.ReadWrite);
        store.Add(cert);
    }

    private static async Task VerifyHashIfPresentAsync(string path, string? expected, CancellationToken ct)
    {
        if (string.IsNullOrWhiteSpace(expected))
            return;

        await using var stream = File.OpenRead(path);
        using var sha = SHA256.Create();
        var actual = Convert.ToHexString(await sha.ComputeHashAsync(stream, ct)).ToLowerInvariant();

        if (!string.Equals(actual, expected.Trim().ToLowerInvariant(), StringComparison.Ordinal))
            throw new InvalidDataException($"SHA-256 inválido: {Path.GetFileName(path)}");
    }
}
