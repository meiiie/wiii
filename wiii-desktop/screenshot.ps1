Add-Type @"
using System;
using System.Runtime.InteropServices;
public class W2 {
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
}
"@

# Minimize everything except Edge
$others = Get-Process | Where-Object { $_.ProcessName -ne 'msedge' -and $_.ProcessName -ne 'explorer' -and $_.MainWindowHandle -ne [IntPtr]::Zero }
foreach ($o in $others) {
    [W2]::ShowWindow($o.MainWindowHandle, 6) | Out-Null
}
Start-Sleep -Milliseconds 500

# Maximize + foreground Edge
$edgeProcs = Get-Process msedge -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne [IntPtr]::Zero }
foreach ($ep in $edgeProcs) {
    [W2]::ShowWindow($ep.MainWindowHandle, 3) | Out-Null
    [W2]::SetForegroundWindow($ep.MainWindowHandle) | Out-Null
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
