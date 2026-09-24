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
    private readonly OriginalVehicleRegistry _vehicleRegistry = new OriginalVehicleRegistryService().Load();
    private Point _dragStart;
    private bool _dragging;
    private readonly AxisAngleRotation3D _rotX = new(new Vector3D(1, 0, 0), 0);
    private readonly AxisAngleRotation3D _rotY = new(new Vector3D(0, 1, 0), 0);
    private FrameworkElement? _hudDragElement;
    private Point _hudDragStart;
    private Point _hudElementStart;
    private string? _liveryTextureSource;

    public MainWindow()
    {
        InitializeComponent();
        var group = new Transform3DGroup();
        group.Children.Add(new RotateTransform3D(_rotX));
        group.Children.Add(new RotateTransform3D(_rotY));
        PreviewVisual.Transform = group;

        RefreshVehicleRegistryUi();
        Log("ReXtreme SDK iniciado como aplicação standalone.");
        Log("O jogo não incorpora o editor; somente o Mod Runtime consumirá os pacotes .rxmod.");
        Log($"Vehicle Registry: {_vehicleRegistry.Archetypes.Count} arquétipos oficiais; {_vehicleRegistry.Profiles.Count} perfis originais verificados.");
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

    private void VerifyPackage_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var dialog = new OpenFileDialog
            {
                Title = "Verificar pacote ReXtreme",
                Filter = "ReXtreme mod|*.rxmod|ZIP|*.zip"
            };
            if (dialog.ShowDialog() != true) return;

            OutputBox.Clear();
            foreach (var item in new RxModPackager().Verify(dialog.FileName))
                Log($"{item.Level,-7} {item.Code}: {item.Message}");
        }
        catch (Exception ex) { Fail(ex); }
    }

    private void AddDependency_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            _projects.AddDependency(DependencyIdBox.Text, DependencyVersionBox.Text);
            DependencyIdBox.Clear();
            DependencyVersionBox.Text = "*";
            RefreshDependencyList();
            Log("Dependência adicionada ao manifest.");
        }
        catch (Exception ex) { Fail(ex); }
    }

    private void RemoveDependency_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            if (DependenciesList.SelectedItem is not ListBoxItem item || item.Tag is not string id)
                return;
            _projects.RemoveDependency(id);
            RefreshDependencyList();
            Log($"Dependência removida: {id}");
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

            var extension = Path.GetExtension(dialog.FileName).ToLowerInvariant();
            var models = Path.Combine(ProjectRoot, "assets", "models");
            var sources = Path.Combine(ProjectRoot, "assets", "source");
            var previews = Path.Combine(ProjectRoot, "assets", ".preview");
            Directory.CreateDirectory(models);
            Directory.CreateDirectory(sources);
            Directory.CreateDirectory(previews);

            var sourceCopy = Path.Combine(sources, Path.GetFileName(dialog.FileName));
            File.Copy(dialog.FileName, sourceCopy, true);

            var blender = BlenderBridgeService.FindBlender();
            string runtimeAsset;

            if (extension == ".glb")
            {
                runtimeAsset = Path.Combine(models, Path.GetFileName(dialog.FileName));
                File.Copy(dialog.FileName, runtimeAsset, true);
            }
            else if (blender is not null)
            {
                runtimeAsset = Path.Combine(models, Path.GetFileNameWithoutExtension(dialog.FileName) + ".glb");
                BlenderBridgeService.ConvertModelToGlb(blender, dialog.FileName, runtimeAsset);
                Log($"Modelo convertido para GLB canônico: {Path.GetFileName(runtimeAsset)}");
            }
            else
            {
                runtimeAsset = Path.Combine(models, Path.GetFileName(dialog.FileName));
                File.Copy(dialog.FileName, runtimeAsset, true);
                Log("Blender não encontrado: fonte preservada sem conversão canônica. Defina BLENDER_PATH para ampliar compatibilidade.");
            }

            if (extension == ".obj")
            {
                PreviewVisual.Content = ObjPreviewLoader.Load(dialog.FileName);
                ViewportHint.Text = Path.GetFileName(dialog.FileName) + " — arraste para girar";
            }
            else if (blender is not null)
            {
                var previewObj = Path.Combine(previews, Path.GetFileNameWithoutExtension(dialog.FileName) + ".obj");
                BlenderBridgeService.ConvertToPreviewObj(blender, dialog.FileName, previewObj);
                PreviewVisual.Content = ObjPreviewLoader.Load(previewObj);
                ViewportHint.Text = Path.GetFileName(dialog.FileName) + " — preview convertido via Blender";
            }
            else
            {
                PreviewVisual.Content = null;
                ViewportHint.Text = Path.GetFileName(dialog.FileName) + " importado; instale/configure Blender para preview 3D deste formato.";
            }

            RefreshProjectTree();
            Log($"Modelo importado: {runtimeAsset}");
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

            var id = string.IsNullOrWhiteSpace(MusicIdBox.Text) || MusicIdBox.Text == "local.music.new-track"
                ? "local.music." + clean
                : MusicIdBox.Text.Trim();
            var title = string.IsNullOrWhiteSpace(MusicTitleBox.Text) || MusicTitleBox.Text == "New Track"
                ? stem
                : MusicTitleBox.Text.Trim();
            var artist = MusicArtistBox.Text.Trim();
            var scope = ((ComboBoxItem)MusicScopeBox.SelectedItem).Content?.ToString() ?? "race";

            var target = _projects.ImportMusic(dialog.FileName, id, title, artist, scope);
            Log($"Música importada: {target} [{scope}]");
            MusicIdBox.Text = "local.music.new-track";
            MusicTitleBox.Text = "New Track";
            MusicArtistBox.Clear();
            RefreshMusicList();
            RefreshProjectTree();
        }
        catch (Exception ex) { Fail(ex); }
    }

    private void CreateVehicle_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            if (VehicleCategoryBox.SelectedItem is not ComboBoxItem archetypeItem || archetypeItem.Tag is not string archetype)
                throw new InvalidOperationException("Selecione um arquétipo original.");
            if (VehicleClassBox.SelectedItem is not ComboBoxItem classItem || classItem.Tag is not string performanceClass)
                throw new InvalidOperationException("Selecione uma classe de performance D–S.");
            if (VehicleBaseProfileBox.SelectedItem is not ComboBoxItem profileItem || profileItem.Tag is not string profileId)
                throw new InvalidOperationException(
                    "Nenhum perfil original verificado está selecionado. Extraia/importe o Original Vehicle Registry antes de criar o veículo.");

            var file = ContentTemplateService.CreateVehicle(
                ProjectRoot,
                VehicleIdBox.Text.Trim(),
                VehicleNameBox.Text.Trim(),
                archetype,
                performanceClass,
                profileId,
                SpeedSlider.Value,
                AccelerationSlider.Value,
                HandlingSlider.Value,
                NitroSlider.Value);
            Log($"Veículo criado: {file}");
            RefreshProjectTree();
        }
        catch (Exception ex) { Fail(ex); }
    }

    private void RefreshVehicleRegistryUi()
    {
        VehicleCategoryBox.Items.Clear();
        foreach (var archetype in _vehicleRegistry.Archetypes)
            VehicleCategoryBox.Items.Add(new ComboBoxItem { Content = archetype.DisplayName, Tag = archetype.Id });

        VehicleClassBox.Items.Clear();
        foreach (var cls in OriginalVehicleRegistryService.PerformanceClasses)
            VehicleClassBox.Items.Add(new ComboBoxItem { Content = $"Class {cls}", Tag = cls });

        if (VehicleCategoryBox.Items.Count > 0) VehicleCategoryBox.SelectedIndex = 0;
        if (VehicleClassBox.Items.Count > 0) VehicleClassBox.SelectedIndex = 0;
        RefreshVehicleProfiles();
    }

    private void VehicleCategoryBox_SelectionChanged(object sender, SelectionChangedEventArgs e) => RefreshVehicleProfiles();
    private void VehicleClassBox_SelectionChanged(object sender, SelectionChangedEventArgs e) => RefreshVehicleProfiles();

    private void RefreshVehicleProfiles()
    {
        if (VehicleBaseProfileBox is null || VehicleProfileStatusText is null) return;
        VehicleBaseProfileBox.Items.Clear();

        var archetype = (VehicleCategoryBox.SelectedItem as ComboBoxItem)?.Tag as string;
        var cls = (VehicleClassBox.SelectedItem as ComboBoxItem)?.Tag as string;
        if (archetype is null || cls is null)
        {
            VehicleProfileStatusText.Text = "Selecione arquétipo e classe.";
            return;
        }

        var matches = _vehicleRegistry.Profiles
            .Where(p => p.Archetype.Equals(archetype, StringComparison.OrdinalIgnoreCase))
            .Where(p => p.PerformanceClass.Equals(cls, StringComparison.OrdinalIgnoreCase))
            .ToArray();

        foreach (var profile in matches)
        {
            var label = string.IsNullOrWhiteSpace(profile.DisplayName)
                ? $"{profile.CarDef} (ID {profile.CarId})"
                : $"{profile.DisplayName} (ID {profile.CarId})";
            VehicleBaseProfileBox.Items.Add(new ComboBoxItem { Content = label, Tag = profile.Id });
        }

        VehicleProfileStatusText.Text = matches.Length == 0
            ? "Nenhum perfil extraído/verificado para este arquétipo e classe."
            : $"{matches.Length} perfil(is) original(is) verificado(s).";
        if (matches.Length > 0) VehicleBaseProfileBox.SelectedIndex = 0;
    }

    private void VehicleBaseProfileBox_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (VehicleBaseProfileBox.SelectedItem is not ComboBoxItem item || item.Tag is not string profileId) return;
        var profile = _vehicleRegistry.Profiles.FirstOrDefault(p => p.Id.Equals(profileId, StringComparison.OrdinalIgnoreCase));
        if (profile?.PerformanceBars is null) return;

        SpeedSlider.Value = profile.PerformanceBars.Speed * 100.0;
        AccelerationSlider.Value = profile.PerformanceBars.Acceleration * 100.0;
        HandlingSlider.Value = profile.PerformanceBars.Handling * 100.0;
        NitroSlider.Value = profile.PerformanceBars.Nitro * 100.0;
    }

    private void CreateEvent_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var mode = ((ComboBoxItem)EventModeBox.SelectedItem).Content?.ToString() ?? "classic";
            var laps = int.TryParse(EventLapsBox.Text, out var parsedLaps) ? Math.Max(1, parsedLaps) : 1;
            var file = ContentTemplateService.SaveEvent(
                ProjectRoot,
                EventIdBox.Text.Trim(),
                EventNameBox.Text.Trim(),
                EventTrackBox.Text.Trim(),
                mode,
                laps,
                EventMusicBox.Text,
                EventHudBox.Text);
            Log($"Evento salvo: {file}");
            RefreshProjectTree();
        }
        catch (Exception ex) { Fail(ex); }
    }

    private void CreateSeason_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var insertMode = ((ComboBoxItem)SeasonInsertModeBox.SelectedItem).Content?.ToString() ?? "new-season";
            var events = Lines(SeasonEventsBox.Text);
            var file = ContentTemplateService.SaveCareerSeason(
                ProjectRoot,
                SeasonIdBox.Text.Trim(),
                SeasonNameBox.Text.Trim(),
                insertMode,
                SeasonTargetBox.Text,
                events);
            Log($"Temporada salva: {file}");
            RefreshProjectTree();
        }
        catch (Exception ex) { Fail(ex); }
    }

    private void CreateSpecialEvent_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var availability = ((ComboBoxItem)SpecialAvailabilityBox.SelectedItem).Content?.ToString() ?? "permanent";
            var file = ContentTemplateService.SaveSpecialEvent(
                ProjectRoot,
                SpecialEventIdBox.Text.Trim(),
                SpecialEventNameBox.Text.Trim(),
                availability,
                Lines(SpecialStagesBox.Text));
            Log($"Evento Especial salvo: {file}");
            RefreshProjectTree();
        }
        catch (Exception ex) { Fail(ex); }
    }

    private void CreateTrack_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var file = ContentTemplateService.CreateTrack(ProjectRoot, "local.track.new", "New Track");
            Log($"Template de pista criado: {file}");
            RefreshProjectTree();
        }
        catch (Exception ex) { Fail(ex); }
    }

    private void CreateLivery_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var file = ContentTemplateService.CreateLivery(ProjectRoot, "local.livery.new", "New Livery", "original.vehicle.pending");
            Log($"Template de pintura/livery criado: {file}");
            RefreshProjectTree();
        }
        catch (Exception ex) { Fail(ex); }
    }

    private void ImportLiveryTexture_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var dialog = new OpenFileDialog
            {
                Title = "Importar textura/decal da pintura",
                Filter = "Texturas|*.png;*.jpg;*.jpeg;*.tga;*.dds;*.tif;*.tiff;*.bmp;*.webp;*.exr;*.hdr"
            };
            if (dialog.ShowDialog() != true) return;
            _liveryTextureSource = _projects.ImportTexture(dialog.FileName);
            LiveryTextureText.Text = _liveryTextureSource;
            Log($"Textura de livery importada: {_liveryTextureSource}");
            RefreshProjectTree();
        }
        catch (Exception ex) { Fail(ex); }
    }

    private void SaveLivery_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var color = LiveryColorBox.Text.Trim();
            if (!Regex.IsMatch(color, "^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$"))
                throw new InvalidDataException("Cor base deve usar HEX, por exemplo #FFFFFF ou #FFFFFFFF.");

            var file = ContentTemplateService.CreateLivery(
                ProjectRoot,
                LiveryIdBox.Text.Trim(),
                LiveryNameBox.Text.Trim(),
                LiveryVehicleBox.Text.Trim(),
                color,
                _liveryTextureSource);
            Log($"Pintura/livery salva: {file}");
            RefreshProjectTree();
        }
        catch (Exception ex) { Fail(ex); }
    }

    private void CreateReplayPreset_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var file = ContentTemplateService.CreateReplayPreset(ProjectRoot, "local.replay.default", "ReXtreme Replay");
            Log($"Preset de Replay criado: {file}");
            RefreshProjectTree();
        }
        catch (Exception ex) { Fail(ex); }
    }

    private void CreatePhotoPreset_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var file = ContentTemplateService.CreatePhotoPreset(ProjectRoot, "local.photo.default", "ReXtreme Photo Mode");
            Log($"Preset de Photo Mode criado: {file}");
            RefreshProjectTree();
        }
        catch (Exception ex) { Fail(ex); }
    }

    private void CreateGraphicsPreset_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var file = ContentTemplateService.CreateGraphicsCapabilityPreset(
                ProjectRoot, "local.graphics.original-capabilities", "Original Renderer Capabilities");
            Log($"Preset gráfico auditável criado: {file}");
            RefreshProjectTree();
        }
        catch (Exception ex) { Fail(ex); }
    }

    private void CreateHud_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var components = new[]
            {
                HudComponent(HudPositionElement, "position", "original-position", "race.position"),
                HudComponent(HudSpeedElement, "speed", "original-speedometer", "player.speed"),
                HudComponent(HudNitroElement, "nitro", "original-nitro", "player.nitro"),
                HudComponent(HudLapElement, "lap", "original-lap", "race.lap"),
                HudComponent(HudTimerElement, "timer", "original-timer", "race.time"),
                HudComponent(HudMiniMapElement, "minimap", "original-minimap", "race.route"),
                HudComponent(HudObjectiveElement, "objective", "original-objective", "race.objective")
            };
            var file = ContentTemplateService.SaveHudLayout(ProjectRoot, "local.hud.custom", components);
            Log($"Layout HUD salvo: {file}");
            RefreshProjectTree();
        }
        catch (Exception ex) { Fail(ex); }
    }

    private RxHudComponent HudComponent(FrameworkElement element, string id, string type, string binding)
    {
        var width = Math.Max(1, HudCanvas.ActualWidth);
        var height = Math.Max(1, HudCanvas.ActualHeight);
        var left = Canvas.GetLeft(element);
        var top = Canvas.GetTop(element);
        if (double.IsNaN(left)) left = 0;
        if (double.IsNaN(top)) top = 0;
        return new RxHudComponent
        {
            Id = id,
            Type = type,
            Binding = binding,
            Anchor = "top-left",
            X = Math.Clamp(left / width, 0, 1),
            Y = Math.Clamp(top / height, 0, 1),
            Scale = 1,
            Opacity = element.Opacity
        };
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
        RefreshDependencyList();
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

    private void RefreshDependencyList()
    {
        DependenciesList.Items.Clear();
        if (_projects.CurrentProjectPath is null) return;
        var manifest = _projects.LoadManifest();
        foreach (var dep in manifest.Dependencies.OrderBy(x => x.Id, StringComparer.OrdinalIgnoreCase))
            DependenciesList.Items.Add(new ListBoxItem { Content = $"{dep.Id}  [{dep.Version}]", Tag = dep.Id });
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

    private void HudElement_MouseLeftButtonDown(object sender, MouseButtonEventArgs e)
    {
        if (sender is not FrameworkElement element) return;
        _hudDragElement = element;
        _hudDragStart = e.GetPosition(HudCanvas);
        var left = Canvas.GetLeft(element);
        var top = Canvas.GetTop(element);
        _hudElementStart = new Point(double.IsNaN(left) ? 0 : left, double.IsNaN(top) ? 0 : top);
        element.CaptureMouse();
        e.Handled = true;
    }

    private void HudElement_MouseMove(object sender, MouseEventArgs e)
    {
        if (_hudDragElement is null || e.LeftButton != MouseButtonState.Pressed) return;
        var p = e.GetPosition(HudCanvas);
        var left = _hudElementStart.X + (p.X - _hudDragStart.X);
        var top = _hudElementStart.Y + (p.Y - _hudDragStart.Y);
        left = Math.Clamp(left, 0, Math.Max(0, HudCanvas.ActualWidth - _hudDragElement.ActualWidth));
        top = Math.Clamp(top, 0, Math.Max(0, HudCanvas.ActualHeight - _hudDragElement.ActualHeight));
        Canvas.SetLeft(_hudDragElement, left);
        Canvas.SetTop(_hudDragElement, top);
        e.Handled = true;
    }

    private void HudElement_MouseLeftButtonUp(object sender, MouseButtonEventArgs e)
    {
        if (_hudDragElement is null) return;
        _hudDragElement.ReleaseMouseCapture();
        _hudDragElement = null;
        e.Handled = true;
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

    private static IEnumerable<string> Lines(string value) =>
        value.Replace("\r", "").Split('\n', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);

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
