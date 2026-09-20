using System;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;
using System.Text.Json;
using Windows.ApplicationModel;
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
        string? certificateSha256,
        string? dependencySha256);

    public sealed record ProgressInfo(double Value, string Status, string Detail);

    private readonly string _payloadDirectory = Path.Combine(AppContext.BaseDirectory, "payload");

    public bool IsInstalled()
    {
        var packageManager = new PackageManager();
        return FindInstalledPackage(packageManager) is not null;
    }

    public Task InstallAsync(IProgress<ProgressInfo> progress, CancellationToken ct = default)
        => DeployAsync(progress, "Instalando Asphalt ReXtreme...", ct);

    public Task RepairAsync(IProgress<ProgressInfo> progress, CancellationToken ct = default)
        => DeployAsync(progress, "Reparando Asphalt ReXtreme...", ct);

    private async Task DeployAsync(
        IProgress<ProgressInfo> progress,
        string deploymentStatus,
        CancellationToken ct)
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

        await VerifyRequiredHashAsync(packagePath, manifest.packageSha256, ct);
        await VerifyRequiredHashAsync(certPath, manifest.certificateSha256, ct);

        if (dependencyPath is not null)
            await VerifyRequiredHashAsync(dependencyPath, manifest.dependencySha256, ct);

        progress.Report(new(
            0.16,
            "Preparando o Windows...",
            "Confiando no certificado local do ReXtreme."));
        TrustPublisherCertificate(certPath);

        var packageUri = new Uri(packagePath, UriKind.Absolute);
        var options = new AddPackageOptions
        {
            ForceAppShutdown = true,
            ForceTargetAppShutdown = true,
            ForceUpdateFromAnyVersion = true,
            RetainFilesOnFailure = true,
        };

        if (dependencyPath is not null)
            options.DependencyPackageUris.Add(new Uri(dependencyPath, UriKind.Absolute));

        progress.Report(new(
            0.28,
            "Preparando dependências...",
            dependencyPath is null
                ? "Verificando runtime instalado."
                : "VC120 x86 será aplicada como dependência local."));

        var packageManager = new PackageManager();
        var operation = packageManager.AddPackageByUriAsync(packageUri, options);

        operation.Progress = (_, deploymentProgress) =>
        {
            var fraction = deploymentProgress.percentage / 100.0;
            progress.Report(new(
                0.32 + fraction * 0.58,
                deploymentStatus,
                "Aplicando o Full Repack e registrando a identidade ReXtreme."));
        };

        using var registration = ct.Register(operation.Cancel);
        var result = await operation;

        if (result.ExtendedErrorCode is not null)
        {
            throw new InvalidOperationException(
                string.IsNullOrWhiteSpace(result.ErrorText)
                    ? result.ExtendedErrorCode.Message
                    : result.ErrorText,
                result.ExtendedErrorCode);
        }

        progress.Report(new(
            0.94,
            "Verificando instalação...",
            "Confirmando a identidade ReXtreme."));

        if (FindInstalledPackage(packageManager) is null)
            throw new InvalidOperationException("O pacote ReXtreme não foi localizado após a instalação.");

        progress.Report(new(
            1.0,
            "Instalação concluída.",
            "Asphalt ReXtreme está pronto para jogar."));
    }

    public async Task LaunchAsync()
    {
        var packageManager = new PackageManager();
        var package = FindInstalledPackage(packageManager)
            ?? throw new InvalidOperationException("Asphalt ReXtreme não está instalado.");

        var entries = await package.GetAppListEntriesAsync();
        var entry = entries.FirstOrDefault()
            ?? throw new InvalidOperationException("O pacote não expõe uma entrada inicializável.");

        if (!await entry.LaunchAsync())
            throw new InvalidOperationException("O Windows recusou a inicialização do jogo.");
    }

    private static Package? FindInstalledPackage(PackageManager packageManager)
        => packageManager
            .FindPackagesForUser(string.Empty)
            .FirstOrDefault(p => string.Equals(
                p.Id.Name,
                "ReXtreme.AsphaltXtreme",
                StringComparison.OrdinalIgnoreCase));

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

    private static async Task VerifyRequiredHashAsync(
        string path,
        string? expected,
        CancellationToken ct)
    {
        if (string.IsNullOrWhiteSpace(expected))
            throw new InvalidDataException(
                $"SHA-256 obrigatório ausente para {Path.GetFileName(path)}.");

        await using var stream = File.OpenRead(path);
        using var sha = SHA256.Create();
        var actual = Convert.ToHexString(
            await sha.ComputeHashAsync(stream, ct)).ToLowerInvariant();

        if (!string.Equals(
            actual,
            expected.Trim().ToLowerInvariant(),
            StringComparison.Ordinal))
        {
            throw new InvalidDataException(
                $"SHA-256 inválido: {Path.GetFileName(path)}");
        }
    }
}
