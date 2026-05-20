$scriptPath = "F:\学习\mimo2codex\npm-global\dist\cli.js"

# Check if already running
$running = Get-CimInstance Win32_Process -Filter "Name='node.exe'" | Where-Object { $_.CommandLine -like "*mimo2codex*" }

if ($running) {
    $running | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
    # Non-blocking balloon tip
    Add-Type -AssemblyName System.Windows.Forms
    $tip = New-Object System.Windows.Forms.NotifyIcon
    $tip.Icon = [System.Drawing.SystemIcons]::Information
    $tip.Visible = $true
    $tip.ShowBalloonTip(3000, "MiMo Proxy", "Proxy stopped", "Info")
    Start-Sleep -Seconds 4
    $tip.Dispose()
} else {
    Start-Process -FilePath "node" -ArgumentList "`"$scriptPath`" --no-admin --no-update-check --data-dir F:\学习\mimo2codex" -NoNewWindow
    Start-Sleep -Seconds 5
    $check = Get-CimInstance Win32_Process -Filter "Name='node.exe'" | Where-Object { $_.CommandLine -like "*mimo2codex*" }
    Add-Type -AssemblyName System.Windows.Forms
    $tip = New-Object System.Windows.Forms.NotifyIcon
    $tip.Icon = [System.Drawing.SystemIcons]::Information
    $tip.Visible = $true
    if ($check) {
        $tip.ShowBalloonTip(3000, "MiMo Proxy", "Proxy started - 127.0.0.1:8788", "Info")
    } else {
        $tip.ShowBalloonTip(3000, "MiMo Proxy", "Failed to start proxy", "Error")
    }
    Start-Sleep -Seconds 4
    $tip.Dispose()
}
