using System.Windows;
using System.Windows.Input;
using System.Windows.Media.Animation;
using System.Windows.Media.Imaging;

namespace AsphaltReXtreme.Setup;

public partial class MainWindow : Window
{
    private readonly InstallerEngine _engine = new();
    private bool _installed;
    private bool _busy;

    public MainWindow()
    {
        InitializeComponent();
    }

    private void Window_Loaded(object sender, RoutedEventArgs e)
    {
        LoadAssets();
        FadeIn(BrandPanel, 0.90, 0.18);
        FadeIn(TrailerPanel, 1.20, 0.42);
        FadeIn(InstallPanel, 0.68, 0.78);
        FadeIn(ActionPanel, 0.58, 1.02);

        _installed = _engine.IsInstalled();
        ApplyInstalledState();
    }

    private void ApplyInstalledState()
    {
        if (_installed)
        {
            StatusText.Text = "Asphalt ReXtreme está instalado.";
            DetailText.Text = "Você pode iniciar o jogo ou reparar os arquivos usando o payload verificado.";
            InstallButton.Content = "JOGAR AGORA";
            RepairButton.Visibility = Visibility.Visible;
        }
        else
        {
            StatusText.Text = "Pronto para instalar.";
            DetailText.Text = "O instalador verificará o pacote antes de alterar o sistema.";
            InstallButton.Content = "INSTALAR";
            RepairButton.Visibility = Visibility.Collapsed;
        }
    }

    private void LoadAssets()
    {
        var root = AppContext.BaseDirectory;
        var logoPath = Path.Combine(root, "assets", "logo.png");
        var trailerPath = Path.Combine(root, "assets", "trailer-vertical.mp4");

        if (File.Exists(logoPath))
        {
            LogoImage.Source = new BitmapImage(new Uri(logoPath, UriKind.Absolute));
        }
        else
        {
            LogoFallback.Visibility = Visibility.Visible;
        }

        if (File.Exists(trailerPath))
        {
            Trailer.Source = new Uri(trailerPath, UriKind.Absolute);
            Trailer.IsMuted = true;
            Trailer.Play();
        }
    }

    private static void FadeIn(UIElement element, double seconds, double delaySeconds)
    {
        var animation = new DoubleAnimation
        {
            From = 0,
            To = 1,
            Duration = TimeSpan.FromSeconds(seconds),
            BeginTime = TimeSpan.FromSeconds(delaySeconds),
            EasingFunction = new QuarticEase { EasingMode = EasingMode.EaseOut }
        };
        element.BeginAnimation(OpacityProperty, animation);
    }

    private async void InstallButton_Click(object sender, RoutedEventArgs e)
    {
        if (_busy)
            return;

        if (_installed)
        {
            await LaunchAsync();
            return;
        }

        await RunDeploymentAsync(
            progress => _engine.InstallAsync(progress),
            "INSTALANDO...");
    }

    private async void RepairButton_Click(object sender, RoutedEventArgs e)
    {
        if (_busy)
            return;

        await RunDeploymentAsync(
            progress => _engine.RepairAsync(progress),
            "REPARANDO...");
    }

    private async Task RunDeploymentAsync(
        Func<IProgress<InstallerEngine.ProgressInfo>, Task> operation,
        string busyLabel)
    {
        try
        {
            _busy = true;
            InstallButton.IsEnabled = false;
            RepairButton.IsEnabled = false;
            InstallButton.Content = busyLabel;

            var progress = new Progress<InstallerEngine.ProgressInfo>(p =>
            {
                StatusText.Text = p.Status;
                DetailText.Text = p.Detail;
                AnimateProgress(p.Value);
            });

            await operation(progress);
            _installed = true;
            ApplyInstalledState();
        }
        catch (Exception ex)
        {
            ShowError(ex);
            InstallButton.Content = _installed ? "JOGAR AGORA" : "TENTAR NOVAMENTE";
        }
        finally
        {
            _busy = false;
            InstallButton.IsEnabled = true;
            RepairButton.IsEnabled = true;
        }
    }

    private async Task LaunchAsync()
    {
        try
        {
            _busy = true;
            InstallButton.IsEnabled = false;
            RepairButton.IsEnabled = false;
            StatusText.Text = "Abrindo Asphalt ReXtreme...";
            await _engine.LaunchAsync();
            Close();
        }
        catch (Exception ex)
        {
            ShowError(ex);
        }
        finally
        {
            _busy = false;
            InstallButton.IsEnabled = true;
            RepairButton.IsEnabled = true;
        }
    }

    private void AnimateProgress(double value)
    {
        value = Math.Clamp(value, 0, 1);
        var width = Math.Max(0, InstallPanel.ActualWidth * value);
        var animation = new DoubleAnimation
        {
            To = width,
            Duration = TimeSpan.FromMilliseconds(520),
            EasingFunction = new CubicEase { EasingMode = EasingMode.EaseOut }
        };
        ProgressFill.BeginAnimation(WidthProperty, animation);
        PercentText.Text = $"{Math.Round(value * 100)}%";
    }

    private void Trailer_MediaOpened(object sender, RoutedEventArgs e)
    {
        Trailer.IsMuted = true;
    }

    private void Trailer_MediaEnded(object sender, RoutedEventArgs e)
    {
        Trailer.Position = TimeSpan.Zero;
        Trailer.Play();
    }

    private void SoundButton_Click(object sender, RoutedEventArgs e)
    {
        Trailer.IsMuted = !Trailer.IsMuted;
        SoundButton.Content = Trailer.IsMuted ? "🔇" : "🔊";
    }

    private void CloseButton_Click(object sender, RoutedEventArgs e) => Close();

    private void Root_MouseLeftButtonDown(object sender, MouseButtonEventArgs e)
    {
        if (e.ButtonState == MouseButtonState.Pressed)
            DragMove();
    }

    private void ShowError(Exception ex)
    {
        StatusText.Text = "Não foi possível concluir.";
        DetailText.Text = ex.Message;
    }
}
