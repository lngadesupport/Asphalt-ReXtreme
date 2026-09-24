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

    public static string ConvertBlendToGlb(string blenderExe, string blendFile, string outputGlb) =>
        ConvertModelToGlb(blenderExe, blendFile, outputGlb);

    public static string ConvertModelToGlb(string blenderExe, string sourceFile, string outputGlb)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(outputGlb)!);
        var extension = Path.GetExtension(sourceFile).ToLowerInvariant();
        var import = extension == ".blend" ? "" : BuildImportExpression(sourceFile, extension);
        var output = PyString(outputGlb);
        var expression =
            import +
            "bpy.ops.export_scene.gltf(filepath=" + output +
            ", export_format='GLB', export_apply=True, export_yup=True)";

        RunBlender(blenderExe, extension == ".blend" ? sourceFile : null, expression, outputGlb);
        return outputGlb;
    }

    public static string ConvertToPreviewObj(string blenderExe, string sourceFile, string outputObj)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(outputObj)!);
        var extension = Path.GetExtension(sourceFile).ToLowerInvariant();
        var import = extension == ".blend" ? "" : BuildImportExpression(sourceFile, extension);
        var output = PyString(outputObj);
        var export =
            "((bpy.ops.wm.obj_export(filepath=" + output + ", export_materials=False)" +
            " if hasattr(bpy.ops.wm, 'obj_export')" +
            " else bpy.ops.export_scene.obj(filepath=" + output + ", use_materials=False)))";
        var expression = import + export;

        RunBlender(blenderExe, extension == ".blend" ? sourceFile : null, expression, outputObj);
        return outputObj;
    }

    private static string BuildImportExpression(string sourceFile, string extension)
    {
        var file = PyString(sourceFile);
        return extension switch
        {
            ".fbx" => "bpy.ops.import_scene.fbx(filepath=" + file + "); ",
            ".gltf" or ".glb" => "bpy.ops.import_scene.gltf(filepath=" + file + "); ",
            ".obj" =>
                "((bpy.ops.wm.obj_import(filepath=" + file + ")" +
                " if hasattr(bpy.ops.wm, 'obj_import')" +
                " else bpy.ops.import_scene.obj(filepath=" + file + "))); ",
            ".dae" => "bpy.ops.wm.collada_import(filepath=" + file + "); ",
            ".stl" =>
                "((bpy.ops.wm.stl_import(filepath=" + file + ")" +
                " if hasattr(bpy.ops.wm, 'stl_import')" +
                " else bpy.ops.import_mesh.stl(filepath=" + file + "))); ",
            ".ply" =>
                "((bpy.ops.wm.ply_import(filepath=" + file + ")" +
                " if hasattr(bpy.ops.wm, 'ply_import')" +
                " else bpy.ops.import_mesh.ply(filepath=" + file + "))); ",
            ".usd" or ".usda" or ".usdc" or ".usdz" => "bpy.ops.wm.usd_import(filepath=" + file + "); ",
            ".3ds" =>
                "(__import__('builtins').getattr(bpy.ops.import_scene, 'autodesk_3ds')(filepath=" + file + ")" +
                " if hasattr(bpy.ops.import_scene, 'autodesk_3ds')" +
                " else (_ for _ in ()).throw(RuntimeError('3DS importer unavailable in this Blender install'))); ",
            _ => throw new NotSupportedException(
                $"O Blender bridge ainda não possui importador registrado para {extension}. " +
                "O arquivo-fonte pode continuar no projeto e receber um conversor adicional depois.")
        };
    }

    private static string PyString(string path) =>
        JsonSerializer.Serialize(Path.GetFullPath(path).Replace('\\', '/'));

    private static void RunBlender(string blenderExe, string? blendFile, string expression, string expectedOutput)
    {
        var psi = new ProcessStartInfo
        {
            FileName = blenderExe,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true
        };

        if (!string.IsNullOrWhiteSpace(blendFile))
            psi.ArgumentList.Add(Path.GetFullPath(blendFile));

        psi.ArgumentList.Add("--background");
        psi.ArgumentList.Add("--python-expr");
        psi.ArgumentList.Add("import bpy; " + expression);

        using var process = Process.Start(psi) ?? throw new InvalidOperationException("Não foi possível iniciar o Blender.");
        var stdout = process.StandardOutput.ReadToEndAsync();
        var stderr = process.StandardError.ReadToEndAsync();

        if (!process.WaitForExit(300000))
        {
            try { process.Kill(true); } catch { }
            throw new TimeoutException("Conversão do Blender excedeu o limite do processo.");
        }

        Task.WaitAll(stdout, stderr);
        if (process.ExitCode != 0 || !File.Exists(expectedOutput))
            throw new InvalidOperationException(
                "Blender não conseguiu converter o modelo. " +
                (string.IsNullOrWhiteSpace(stderr.Result) ? stdout.Result : stderr.Result));
    }
}
