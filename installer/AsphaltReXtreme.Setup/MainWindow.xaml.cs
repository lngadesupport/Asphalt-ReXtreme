using System;
using System.IO;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Input;
using System.Windows.Media.Animation;
using System.Windows.Media.Imaging;

namespace AsphaltReXtreme.Setup;

public partial class MainWindow : Window
{
    private readonly InstallerEngine _engine = new();
    private bool _installed;
    private bool _repairRequired;
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
        RefreshInstalledState();
    }

    private void RefreshInstalledState()
    {
        var state = _engine.GetInstalledState();
        _installed = state.IsInstalled && state.IsHealthy;
        _repairRequired = state.IsInstalled && !state.IsHealthy;

        if (_installed)
        {
            StatusText.Text = "Asphalt ReXtreme já está instalado.";
            DetailText.Text = $"Versão {state.Version} • instalação verificada pelo Windows.";
            InstallButton.Content = "JOGAR AGORA";
            RepairButton.Visibility = Visibility.Visible;
            AnimateProgress(1.0);
        }
        else if (_repairRequired)
        {
            StatusText.Text = "A instalação precisa de reparo.";
            DetailText.Text = "O Windows detectou arquivos ausentes, modificados ou indisponíveis.";
            InstallButton.Content = "REPARAR";
            RepairButton.Visibility = Visibility.Collapsed;
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
            LogoImage.Source = new BitmapImage(
                new System.Uri(logoPath, System.UriKind.Absolute));
        }
        else
        {
            LogoFallback.Visibility = Visibility.Visible;
        }

        if (File.Exists(trailerPath))
        {
            Trailer.Source = new System.Uri(
                trailerPath,
                System.UriKind.Absolute);
            Trailer.IsMuted = true;
            Trailer.Play();
        }
    }

    private static void FadeIn(
        UIElement element,
        double seconds,
        double delaySeconds)
    {
        var animation = new DoubleAnimation
        {
            From = 0,
            To = 1,
            Duration = TimeSpan.FromSeconds(seconds),
            BeginTime = TimeSpan.FromSeconds(delaySeconds),
            EasingFunction = new QuarticEase
            {
                EasingMode = EasingMode.EaseOut
            }
        };
        element.BeginAnimation(OpacityProperty, animation);
    }

    private async void InstallButton_Click(
        object sender,
        RoutedEventArgs e)
    {
        if (_busy)
            return;

        if (_installed)
        {
            await LaunchGameAsync();
            return;
        }

        await RunInstallAsync(_repairRequired);
    }

    private async void RepairButton_Click(
        object sender,
        RoutedEventArgs e)
    {
        if (_busy)
            return;

        await RunInstallAsync(repair: true);
    }

    private async Task RunInstallAsync(bool repair)
    {
        try
        {
            SetBusy(true);
            InstallButton.Content = repair ? "REPARANDO..." : "INSTALANDO...";

            var progress = new Progress<InstallerEngine.ProgressInfo>(p =>
            {
                StatusText.Text = p.Status;
                DetailText.Text = p.Detail;
                AnimateProgress(p.Value);
            });

            await _engine.InstallAsync(progress, repair);
            RefreshInstalledState();
        }
        catch (Exception ex)
        {
            ShowError(ex);
            InstallButton.Content = repair
                ? "TENTAR REPARO NOVAMENTE"
                : "TENTAR NOVAMENTE";
        }
        finally
        {
            SetBusy(false);
        }
    }

    private async Task LaunchGameAsync()
    {
        try
        {
            SetBusy(true);
            StatusText.Text = "Abrindo Asphalt ReXtreme...";
            DetailText.Text = "Iniciando a identidade local ReXtreme.";
            await _engine.LaunchAsync();
            Close();
        }
        catch (Exception ex)
        {
            ShowError(ex);
            RefreshInstalledState();
        }
        finally
        {
            SetBusy(false);
        }
    }

    private void SetBusy(bool busy)
    {
        _busy = busy;
        InstallButton.IsEnabled = !busy;
        RepairButton.IsEnabled = !busy;
    }

    private void AnimateProgress(double value)
    {
        value = Math.Clamp(value, 0, 1);
        var width = Math.Max(0, InstallPanel.ActualWidth * value);
        var animation = new DoubleAnimation
        {
            To = width,
            Duration = TimeSpan.FromMilliseconds(520),
            EasingFunction = new CubicEase
            {
                EasingMode = EasingMode.EaseOut
            }
        };
        ProgressFill.BeginAnimation(WidthProperty, animation);
        PercentText.Text = $"{Math.Round(value * 100)}%";
    }

    private void Trailer_MediaOpened(
        object sender,
        RoutedEventArgs e)
    {
        Trailer.IsMuted = true;
    }

    private void Trailer_MediaEnded(
        object sender,
        RoutedEventArgs e)
    {
        Trailer.Position = TimeSpan.Zero;
        Trailer.Play();
    }

    private void SoundButton_Click(
        object sender,
        RoutedEventArgs e)
    {
        Trailer.IsMuted = !Trailer.IsMuted;
        SoundButton.Content = Trailer.IsMuted ? "🔇" : "🔊";
    }

    private void CloseButton_Click(
        object sender,
        RoutedEventArgs e) => Close();

    private void Root_MouseLeftButtonDown(
        object sender,
        MouseButtonEventArgs e)
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
