using System.Diagnostics;
using System.Security.Cryptography;
using System.Text.Json;

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

        progress.Report(new(0.18, "Preparando o Windows...", "Confiando no certificado local do ReXtreme."));
        await RunPowerShellAsync(
            $"Import-Certificate -FilePath {PsQuote(certPath)} -CertStoreLocation 'Cert:\\LocalMachine\\TrustedPeople' | Out-Null",
            ct);

        progress.Report(new(
            0.34,
            "Preparando dependências...",
            dependencyPath is null
                ? "A dependência VC120 deve já estar instalada."
                : "VC120 x86 será instalada junto com o jogo."));

        progress.Report(new(0.48, "Instalando Asphalt ReXtreme...", "Registrando o pacote independente ReXtreme."));

        string installCommand;
        if (dependencyPath is not null)
        {
            installCommand =
                $"Add-AppxPackage -Path {PsQuote(packagePath)} -DependencyPath {PsQuote(dependencyPath)} " +
                "-ForceApplicationShutdown -RetainFilesOnFailure";
        }
        else
        {
            installCommand =
                $"Add-AppxPackage -Path {PsQuote(packagePath)} -ForceApplicationShutdown -RetainFilesOnFailure";
        }

        await RunPowerShellAsync(installCommand, ct);

        progress.Report(new(0.90, "Verificando instalação...", "Confirmando a identidade ReXtreme."));
        await RunPowerShellAsync(
            "$p = Get-AppxPackage -Name 'ReXtreme.AsphaltXtreme' -ErrorAction Stop; " +
            "if (-not $p) { throw 'Package not found after install.' }",
            ct);

        progress.Report(new(1.0, "Instalação concluída.", "Asphalt ReXtreme está pronto para jogar."));
    }

    public async Task LaunchAsync(CancellationToken ct = default)
    {
        const string script =
            "$p = Get-AppxPackage -Name 'ReXtreme.AsphaltXtreme' -ErrorAction Stop; " +
            "$m = Get-AppxPackageManifest $p; " +
            "$id = $m.Package.Applications.Application[0].Id; " +
            "$target = 'shell:AppsFolder\\' + $p.PackageFamilyName + '!' + $id; " +
            "Start-Process explorer.exe $target;";
        await RunPowerShellAsync(script, ct);
    }

    private string RequirePayload(string fileName)
    {
        var path = Path.Combine(_payloadDirectory, fileName);
        if (!File.Exists(path))
            throw new FileNotFoundException($"Arquivo obrigatório ausente: {fileName}", path);
        return path;
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

    private static string PsQuote(string value) => "'" + value.Replace("'", "''") + "'";

    private static async Task RunPowerShellAsync(string command, CancellationToken ct)
    {
        var psi = new ProcessStartInfo
        {
            FileName = "powershell.exe",
            Arguments = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -Command " + QuoteArgument(command),
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            WindowStyle = ProcessWindowStyle.Hidden,
        };

        using var process = new Process { StartInfo = psi };
        process.Start();

        var stdoutTask = process.StandardOutput.ReadToEndAsync(ct);
        var stderrTask = process.StandardError.ReadToEndAsync(ct);
        await process.WaitForExitAsync(ct);
        var stdout = await stdoutTask;
        var stderr = await stderrTask;

        if (process.ExitCode != 0)
        {
            var message = string.IsNullOrWhiteSpace(stderr) ? stdout : stderr;
            throw new InvalidOperationException(message.Trim());
        }
    }

    private static string QuoteArgument(string value)
        => """ + value.Replace("\\", "\\\\").Replace(""", "\\"") + """;
}
