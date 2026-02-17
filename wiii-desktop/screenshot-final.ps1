Add-Type @"
using System;
using System.Runtime.InteropServices;
public class W6 {
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
}
"@

# Kill distractions
Stop-Process -Name WINWORD -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500

# Minimize everything
$all = Get-Process | Where-Object { $_.MainWindowHandle -ne [IntPtr]::Zero }
foreach ($p in $all) { [W6]::ShowWindow($p.MainWindowHandle, 6) | Out-Null }
Start-Sleep -Seconds 1

# Kill Chrome, open fresh incognito to localhost:1420
Stop-Process -Name chrome -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3
Start-Process 'C:\Program Files\Google\Chrome\Application\chrome.exe' -ArgumentList '--incognito', '--start-maximized', '--no-first-run', 'http://localhost:1420/'
Start-Sleep -Seconds 8

# Maximize + foreground Chrome
$chrome = Get-Process chrome -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne [IntPtr]::Zero }
foreach ($c in $chrome) {
    [W6]::ShowWindow($c.MainWindowHandle, 3) | Out-Null
    [W6]::SetForegroundWindow($c.MainWindowHandle) | Out-Null
}
Start-Sleep -Seconds 2

# Screenshot
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bitmap = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)
$bitmap.Save('E:\Sach\Sua\AI_v1\wiii-desktop\screenshot-82b-final.png', [System.Drawing.Imaging.ImageFormat]::Png)
$graphics.Dispose()
$bitmap.Dispose()
Write-Output 'Done'
