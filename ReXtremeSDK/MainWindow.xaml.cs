using Microsoft.Win32;
using ReXtremeSDK.Core;
using ReXtremeSDK.Preview;
using System.Text.RegularExpressions;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media.Media3D;

namespace ReXtremeSDK;

public partial class MainWindow : Window
{
    private readonly ProjectService _projects = new();
    private Point _dragStart;
    private bool _dragging;
    private readonly AxisAngleRotation3D _rotX = new(new Vector3D(1, 0, 0), 0);
    private readonly AxisAngleRotation3D _rotY = new(new Vector3D(0, 1, 0), 0);

    public MainWindow()
    {
        InitializeComponent();
        var group = new Transform3DGroup();
        group.Children.Add(new RotateTransform3D(_rotX));
        group.Children.Add(new RotateTransform3D(_rotY));
        PreviewVisual.Transform = group;

        Log("ReXtreme SDK iniciado como aplicação standalone.");
        Log("O jogo não incorpora o editor; somente o Mod Runtime consumirá os pacotes .rxmod.");
    }

    private string ProjectRoot =>
        _projects.CurrentProjectPath ?? throw new InvalidOperationException("Abra ou crie um projeto primeiro.");

    private void NewProject_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var dialog = new SaveFileDialog
            {
                Title = "Escolha a pasta do novo projeto",
                Filter = "ReXtreme manifest|manifest.json",
                FileName = "manifest.json",
                AddExtension = false,
                OverwritePrompt = false
            };
            if (dialog.ShowDialog() != true) return;

            var root = Path.GetDirectoryName(dialog.FileName)!;
            var folderName = new DirectoryInfo(root).Name;
            var clean = Regex.Replace(folderName.ToLowerInvariant(), "[^a-z0-9]+", "-").Trim('-');
            if (string.IsNullOrWhiteSpace(clean)) clean = "project";

            _projects.CreateProject(root, $"local.rextreme.{clean}", folderName, "full-expansion");
            LoadProjectUi();
            Log($"Projeto criado: {root}");
        }
        catch (Exception ex) { Fail(ex); }
    }

    private void OpenProject_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var dialog = new OpenFileDialog
            {
                Title = "Abra o manifest.json de um projeto ReXtreme SDK",
                Filter = "ReXtreme manifest|manifest.json|JSON|*.json"
            };
            if (dialog.ShowDialog() != true) return;
            _projects.OpenProject(Path.GetDirectoryName(dialog.FileName)!);
            LoadProjectUi();
            Log($"Projeto aberto: {ProjectRoot}");
        }
        catch (Exception ex) { Fail(ex); }
    }

    private void Validate_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            OutputBox.Clear();
            foreach (var item in _projects.Validate())
                Log($"{item.Level,-5} {item.Code}: {item.Message}" + (item.Path is null ? "" : $" [{item.Path}]"));
        }
        catch (Exception ex) { Fail(ex); }
    }

    private void Build_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var manifest = _projects.LoadManifest();
            var dialog = new SaveFileDialog
            {
                Title = "Gerar pacote ReXtreme",
                Filter = "ReXtreme mod|*.rxmod",
                FileName = SafeName(manifest.Name) + ".rxmod",
                DefaultExt = ".rxmod"
            };
            if (dialog.ShowDialog() != true) return;

            var output = new RxModPackager().Build(ProjectRoot, dialog.FileName);
            Log($"BUILD OK: {output}");
            StatusText.Text = "Pacote .rxmod gerado com sucesso.";
        }
        catch (Exception ex) { Fail(ex); }
    }

    private void ImportModel_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var dialog = new OpenFileDialog
            {
                Title = "Importar modelo 3D",
                Filter = "Modelos 3D|*.obj;*.fbx;*.gltf;*.glb;*.dae;*.3ds;*.ply;*.stl;*.blend;*.usd;*.usda;*.usdc;*.usdz|Todos os arquivos|*.*"
            };
            if (dialog.ShowDialog() != true) return;

            var models = Path.Combine(ProjectRoot, "assets", "models");
            Directory.CreateDirectory(models);
            var target = Path.Combine(models, Path.GetFileName(dialog.FileName));
            File.Copy(dialog.FileName, target, true);

            if (Path.GetExtension(target).Equals(".obj", StringComparison.OrdinalIgnoreCase))
            {
                PreviewVisual.Content = ObjPreviewLoader.Load(target);
                ViewportHint.Text = Path.GetFileName(target) + " — arraste para girar";
            }
            else
            {
                PreviewVisual.Content = null;
                ViewportHint.Text = Path.GetFileName(target) + " importado; preview/conversor deste formato entra no pipeline DCC.";
            }
            RefreshProjectTree();
            Log($"Modelo importado: {target}");
        }
        catch (Exception ex) { Fail(ex); }
    }

    private void ImportMusic_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var dialog = new OpenFileDialog
            {
                Title = "Importar música",
                Filter = "Áudio suportado|*.wav;*.flac;*.ogg;*.mp3;*.aac;*.m4a"
            };
            if (dialog.ShowDialog() != true) return;

            var stem = Path.GetFileNameWithoutExtension(dialog.FileName);
            var clean = Regex.Replace(stem.ToLowerInvariant(), "[^a-z0-9]+", "-").Trim('-');
            if (string.IsNullOrWhiteSpace(clean)) clean = "track";
            var id = "local.music." + clean;
            var target = _projects.ImportMusic(dialog.FileName, id, stem, "", "race");
            Log($"Música importada: {target}");
            RefreshMusicList();
            RefreshProjectTree();
        }
        catch (Exception ex) { Fail(ex); }
    }

    private void CreateVehicle_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var category = ((ComboBoxItem)VehicleCategoryBox.SelectedItem).Content?.ToString() ?? "rally";
            var file = ContentTemplateService.CreateVehicle(
                ProjectRoot,
                VehicleIdBox.Text.Trim(),
                VehicleNameBox.Text.Trim(),
                category,
                VehicleBaseProfileBox.Text.Trim(),
                SpeedSlider.Value,
                AccelerationSlider.Value,
                HandlingSlider.Value,
                NitroSlider.Value);
            Log($"Veículo criado: {file}");
            RefreshProjectTree();
        }
        catch (Exception ex) { Fail(ex); }
    }

    private void CreateEvent_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var file = ContentTemplateService.CreateEvent(
                ProjectRoot, "local.event.new-event", "New Event", "original.track.pending", "classic", 1);
            Log($"Template de evento criado: {file}");
            RefreshProjectTree();
        }
        catch (Exception ex) { Fail(ex); }
    }

    private void CreateSeason_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var file = ContentTemplateService.CreateCareerSeason(ProjectRoot, "local.career.new-season", "New Season");
            Log($"Template de temporada criado: {file}");
            RefreshProjectTree();
        }
        catch (Exception ex) { Fail(ex); }
    }

    private void CreateHud_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var file = ContentTemplateService.CreateHudLayout(ProjectRoot, "local.hud.custom");
            Log($"Layout HUD criado: {file}");
            RefreshProjectTree();
        }
        catch (Exception ex) { Fail(ex); }
    }

    private void LoadProjectUi()
    {
        var manifest = _projects.LoadManifest();
        ProjectPathText.Text = ProjectRoot;
        InspectorProjectName.Text = manifest.Name;
        InspectorProjectId.Text = manifest.Id;
        InspectorProjectType.Text = manifest.Type;
        RefreshProjectTree();
        RefreshMusicList();
        StatusText.Text = "Projeto carregado.";
    }

    private void RefreshProjectTree()
    {
        ProjectTree.Items.Clear();
        if (_projects.CurrentProjectPath is null) return;
        var root = new TreeViewItem { Header = new DirectoryInfo(ProjectRoot).Name, IsExpanded = true };
        AddDirectory(root, ProjectRoot, 0);
        ProjectTree.Items.Add(root);
    }

    private static void AddDirectory(TreeViewItem parent, string directory, int depth)
    {
        if (depth > 4) return;
        foreach (var dir in Directory.EnumerateDirectories(directory).OrderBy(Path.GetFileName))
        {
            var item = new TreeViewItem { Header = Path.GetFileName(dir) };
            AddDirectory(item, dir, depth + 1);
            parent.Items.Add(item);
        }
        foreach (var file in Directory.EnumerateFiles(directory).OrderBy(Path.GetFileName))
            parent.Items.Add(new TreeViewItem { Header = Path.GetFileName(file) });
    }

    private void RefreshMusicList()
    {
        MusicList.Items.Clear();
        if (_projects.CurrentProjectPath is null) return;
        var path = Path.Combine(ProjectRoot, "content", "music.json");
        if (!File.Exists(path)) return;
        try
        {
            var catalog = ProjectService.LoadJson<RxMusicCatalog>(path);
            foreach (var track in catalog.Tracks)
                MusicList.Items.Add($"{track.Title}  —  {track.Scope}  [{track.Id}]");
        }
        catch (Exception ex) { Log("MUSIC CATALOG ERROR: " + ex.Message); }
    }

    private void Viewport_MouseDown(object sender, MouseButtonEventArgs e)
    {
        if (e.LeftButton != MouseButtonState.Pressed) return;
        _dragging = true;
        _dragStart = e.GetPosition(ModelViewport);
        ModelViewport.CaptureMouse();
    }

    private void Viewport_MouseMove(object sender, MouseEventArgs e)
    {
        if (!_dragging) return;
        var p = e.GetPosition(ModelViewport);
        var dx = p.X - _dragStart.X;
        var dy = p.Y - _dragStart.Y;
        _rotY.Angle += dx * 0.45;
        _rotX.Angle += dy * 0.45;
        _dragStart = p;
    }

    private void Viewport_MouseUp(object sender, MouseButtonEventArgs e)
    {
        _dragging = false;
        ModelViewport.ReleaseMouseCapture();
    }

    private static string SafeName(string value)
    {
        var invalid = Path.GetInvalidFileNameChars();
        return string.Concat(value.Select(c => invalid.Contains(c) ? '_' : c));
    }

    private void Log(string message)
    {
        OutputBox.AppendText(message + Environment.NewLine);
        OutputBox.ScrollToEnd();
    }

    private void Fail(Exception ex)
    {
        Log("ERROR: " + ex.Message);
        StatusText.Text = "Erro — consulte Output.";
    }
}
