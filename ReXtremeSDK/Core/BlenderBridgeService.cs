using System.Diagnostics;
using System.Text.Json;

namespace ReXtremeSDK.Core;

public static class BlenderBridgeService
{
    public static string? FindBlender()
    {
        var explicitPath = Environment.GetEnvironmentVariable("BLENDER_PATH");
        if (!string.IsNullOrWhiteSpace(explicitPath) && File.Exists(explicitPath))
            return explicitPath;

        var roots = new[]
        {
            Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),
            Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86)
        }.Where(Directory.Exists);

        foreach (var root in roots)
        {
            var foundation = Path.Combine(root, "Blender Foundation");
            if (!Directory.Exists(foundation)) continue;

            var match = Directory.EnumerateFiles(foundation, "blender.exe", SearchOption.AllDirectories)
                .OrderByDescending(x => x, StringComparer.OrdinalIgnoreCase)
                .FirstOrDefault();
            if (match is not null) return match;
        }
        return null;
    }

    public static string ConvertBlendToGlb(string blenderExe, string blendFile, string outputGlb)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(outputGlb)!);

        var outJson = JsonSerializer.Serialize(Path.GetFullPath(outputGlb).Replace('\\', '/'));
        var expression =
            "import bpy; " +
            "bpy.ops.export_scene.gltf(filepath=" + outJson + ", export_format='GLB', export_apply=True, export_yup=True)";

        var psi = new ProcessStartInfo
        {
            FileName = blenderExe,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true
        };
        psi.ArgumentList.Add(Path.GetFullPath(blendFile));
        psi.ArgumentList.Add("--background");
        psi.ArgumentList.Add("--python-expr");
        psi.ArgumentList.Add(expression);

        using var process = Process.Start(psi) ?? throw new InvalidOperationException("Não foi possível iniciar o Blender.");
        var stdout = process.StandardOutput.ReadToEndAsync();
        var stderr = process.StandardError.ReadToEndAsync();

        if (!process.WaitForExit(300000))
        {
            try { process.Kill(true); } catch { }
            throw new TimeoutException("Conversão do Blender excedeu o limite do processo.");
        }

        Task.WaitAll(stdout, stderr);
        if (process.ExitCode != 0 || !File.Exists(outputGlb))
            throw new InvalidOperationException(
                "Blender não conseguiu exportar o GLB. " +
                (string.IsNullOrWhiteSpace(stderr.Result) ? stdout.Result : stderr.Result));

        return outputGlb;
    }
}
