using System;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;
using System.Threading;
using System.Threading.Tasks;
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
        string? dependencySha256,
        string? packageSha256,
        string? certificateSha256,
        bool releaseEligible);

    public sealed record ProgressInfo(double Value, string Status, string Detail);

    public sealed record InstalledState(
        bool IsInstalled,
        bool IsHealthy,
        string? Version);

    private const string PackageName = "ReXtreme.AsphaltXtreme";
    private readonly string _payloadDirectory = Path.Combine(AppContext.BaseDirectory, "payload");

    public InstalledState GetInstalledState()
    {
        var package = FindInstalledPackage();
        if (package is null)
            return new(false, false, null);

        var version = package.Id.Version;
        var versionText = $"{version.Major}.{version.Minor}.{version.Build}.{version.Revision}";
        return new(true, package.Status.VerifyIsOK(), versionText);
    }

    public async Task InstallAsync(
        IProgress<ProgressInfo> progress,
        bool repair = false,
        CancellationToken ct = default)
    {
        progress.Report(new(0.04, "Verificando arquivos...", "Validando o payload do ReXtreme."));

        var manifestPath = Path.Combine(_payloadDirectory, "install-manifest.json");
        if (!File.Exists(manifestPath))
            throw new FileNotFoundException("install-manifest.json não foi encontrado.", manifestPath);

        var json = await File.ReadAllTextAsync(manifestPath, ct);
        var manifest = System.Text.Json.JsonSerializer.Deserialize<InstallManifest>(
            json,
            new System.Text.Json.JsonSerializerOptions { PropertyNameCaseInsensitive = true })
            ?? throw new InvalidDataException("Manifesto de instalação inválido.");

        if (!manifest.releaseEligible)
            throw new InvalidDataException(
                "Este payload é apenas diagnóstico e não atende ao gate do RC1.");

        var packagePath = RequirePayload(manifest.package);
        var certPath = RequirePayload(manifest.certificate);
        var dependencyPath = string.IsNullOrWhiteSpace(manifest.dependency)
            ? null
            : RequirePayload(manifest.dependency);

        if (dependencyPath is null)
            throw new InvalidDataException("O runtime VC120 x86 não está presente no payload.");

        await VerifyHashIfPresentAsync(packagePath, manifest.packageSha256, ct);
        await VerifyHashIfPresentAsync(certPath, manifest.certificateSha256, ct);
        await VerifyHashIfPresentAsync(dependencyPath, manifest.dependencySha256, ct);

        progress.Report(new(
            0.15,
            repair ? "Preparando reparo..." : "Preparando o Windows...",
            "Validando o certificado local do ReXtreme."));
        TrustPublisherCertificate(certPath);

        var packageUri = new System.Uri(packagePath, System.UriKind.Absolute);
        var dependencyUri = new System.Uri(dependencyPath, System.UriKind.Absolute);

        var options = new AddPackageOptions
        {
            ForceAppShutdown = true,
            ForceUpdateFromAnyVersion = repair,
            RetainFilesOnFailure = true,
        };
        options.DependencyPackageUris.Add(dependencyUri);

        var packageManager = new PackageManager();
        var operation = packageManager.AddPackageByUriAsync(packageUri, options);

        operation.Progress = (_, deploymentProgress) =>
        {
            var fraction = deploymentProgress.percentage / 100.0;
            progress.Report(new(
                0.25 + fraction * 0.66,
                repair ? "Reparando Asphalt ReXtreme..." : "Instalando Asphalt ReXtreme...",
                repair
                    ? "Reaplicando o pacote verificado sem apagar o progresso local."
                    : "Aplicando o Full Repack e registrando a identidade ReXtreme."));
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

        progress.Report(new(0.94, "Verificando instalação...", "Confirmando integridade e identidade ReXtreme."));
        var installed = FindInstalledPackage()
            ?? throw new InvalidOperationException(
                "O pacote ReXtreme não foi localizado após a instalação.");

        if (!installed.Status.VerifyIsOK())
            throw new InvalidOperationException(
                "O Windows registrou o pacote, mas a verificação de integridade não passou.");

        progress.Report(new(
            1.0,
            repair ? "Reparo concluído." : "Instalação concluída.",
            "Asphalt ReXtreme está pronto para jogar."));
    }

    public async Task LaunchAsync()
    {
        var package = FindInstalledPackage()
            ?? throw new InvalidOperationException("Asphalt ReXtreme não está instalado.");

        if (!package.Status.VerifyIsOK())
            throw new InvalidOperationException(
                "A instalação precisa ser reparada antes de iniciar o jogo.");

        var entries = await package.GetAppListEntriesAsync();
        var entry = entries.FirstOrDefault()
            ?? throw new InvalidOperationException(
                "O pacote não expõe uma entrada inicializável.");

        if (!await entry.LaunchAsync())
            throw new InvalidOperationException(
                "O Windows recusou a inicialização do jogo.");
    }

    private static Package? FindInstalledPackage()
    {
        var packageManager = new PackageManager();
        return packageManager
            .FindPackagesForUser(string.Empty)
            .FirstOrDefault(p => string.Equals(
                p.Id.Name,
                PackageName,
                StringComparison.OrdinalIgnoreCase));
    }

    private string RequirePayload(string fileName)
    {
        var path = Path.GetFullPath(Path.Combine(_payloadDirectory, fileName));
        var root = Path.GetFullPath(_payloadDirectory) + Path.DirectorySeparatorChar;

        if (!path.StartsWith(root, StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException(
                "O manifesto de instalação contém um caminho inválido.");

        if (!File.Exists(path))
            throw new FileNotFoundException(
                $"Arquivo obrigatório ausente: {fileName}",
                path);

        return path;
    }

    private static void TrustPublisherCertificate(string path)
    {
        using var cert = new X509Certificate2(path);
        using var store = new X509Store(
            StoreName.TrustedPeople,
            StoreLocation.LocalMachine);

        store.Open(OpenFlags.ReadWrite);

        var alreadyTrusted = store.Certificates
            .Find(X509FindType.FindByThumbprint, cert.Thumbprint, validOnly: false)
            .Count > 0;

        if (!alreadyTrusted)
            store.Add(cert);
    }

    private static async Task VerifyHashIfPresentAsync(
        string path,
        string? expected,
        CancellationToken ct)
    {
        if (string.IsNullOrWhiteSpace(expected))
            throw new InvalidDataException(
                $"SHA-256 ausente no manifesto: {Path.GetFileName(path)}");

        await using var stream = File.OpenRead(path);
        using var sha = SHA256.Create();
        var actual = Convert
            .ToHexString(await sha.ComputeHashAsync(stream, ct))
            .ToLowerInvariant();

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
