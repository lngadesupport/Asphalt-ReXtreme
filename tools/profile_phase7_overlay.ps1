param(
    [string]$GameRoot = "",
    [string]$StatusFile = ""
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

if ([string]::IsNullOrWhiteSpace($GameRoot)) {
    $pkg = Get-AppxPackage -Name "A278AB0D.AsphaltXtreme" -ErrorAction Stop |
        Sort-Object Version -Descending |
        Select-Object -First 1
    $GameRoot = $pkg.InstallLocation
}

if ([string]::IsNullOrWhiteSpace($StatusFile)) {
    $StatusFile = Join-Path $GameRoot "_PROFILE_PHASE7_STATUS.txt"
}

if (-not (Test-Path -LiteralPath $StatusFile)) {
    "Carregando perfil..." | Set-Content -LiteralPath $StatusFile -Encoding UTF8
}

$form = New-Object Windows.Forms.Form
$form.FormBorderStyle = [Windows.Forms.FormBorderStyle]::None
$form.StartPosition = [Windows.Forms.FormStartPosition]::Manual
$form.TopMost = $true
$form.ShowInTaskbar = $false
$form.BackColor = [Drawing.Color]::FromArgb(28,28,28)
$form.Opacity = 0.88
$form.Width = 310
$form.Height = 48

$wa = [Windows.Forms.Screen]::PrimaryScreen.WorkingArea
$form.Location = New-Object Drawing.Point(($wa.Right - $form.Width - 18), ($wa.Top + 18))

$label = New-Object Windows.Forms.Label
$label.Dock = [Windows.Forms.DockStyle]::Fill
$label.TextAlign = [Drawing.ContentAlignment]::MiddleCenter
$label.ForeColor = [Drawing.Color]::White
$label.Font = New-Object Drawing.Font("Segoe UI",11,[Drawing.FontStyle]::Bold)
$label.Text = "Carregando perfil..."
$form.Controls.Add($label)

$timer = New-Object Windows.Forms.Timer
$timer.Interval = 250
$timer.Add_Tick({
    try {
        if (Test-Path -LiteralPath $StatusFile) {
            $txt = (Get-Content -LiteralPath $StatusFile -Raw -ErrorAction Stop).Trim()
            if (-not [string]::IsNullOrWhiteSpace($txt)) {
                $label.Text = $txt
            }
        }
        $ams = Get-Process -Name "AMS" -ErrorAction SilentlyContinue
        if (-not $ams) {
            $form.Close()
        }
    } catch {}
})
$timer.Start()

[void]$form.ShowDialog()
