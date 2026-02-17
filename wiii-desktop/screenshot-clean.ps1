Add-Type @"
using System;
using System.Runtime.InteropServices;
public class W3 {
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
}
"@

# Minimize EVERYTHING
$all = Get-Process | Where-Object { $_.MainWindowHandle -ne [IntPtr]::Zero }
foreach ($p in $all) { [W3]::ShowWindow($p.MainWindowHandle, 6) | Out-Null }
Start-Sleep -Seconds 1

# Kill Edge, reopen fresh maximized
Stop-Process -Name msedge -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Start-Process 'msedge' -ArgumentList '--inprivate', '--start-maximized', '--no-first-run', 'http://localhost:1420'
Start-Sleep -Seconds 6

# Find Edge, maximize + foreground
$edge = Get-Process msedge -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne [IntPtr]::Zero }
foreach ($e in $edge) {
    [W3]::ShowWindow($e.MainWindowHandle, 3) | Out-Null
    [W3]::SetForegroundWindow($e.MainWindowHandle) | Out-Null
}
Start-Sleep -Seconds 2

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
