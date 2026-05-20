$scriptPath = "C:\Users\Administrator\AppData\Roaming\npm\node_modules\mimo2codex\dist\cli.js"

# Check if already running
$running = Get-CimInstance Win32_Process -Filter "Name='node.exe'" | Where-Object { $_.CommandLine -like "*mimo2codex*" }

if ($running) {
    $running | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show("MiMo proxy stopped", "MiMo Proxy", "OK", "Information")
} else {
    Start-Process -FilePath "node" -ArgumentList "`"$scriptPath`" --no-admin --no-update-check" -NoNewWindow
    Start-Sleep -Seconds 5
    $check = Get-CimInstance Win32_Process -Filter "Name='node.exe'" | Where-Object { $_.CommandLine -like "*mimo2codex*" }
    Add-Type -AssemblyName System.Windows.Forms
    if ($check) {
        [System.Windows.Forms.MessageBox]::Show("MiMo proxy started`n127.0.0.1:8788", "MiMo Proxy", "OK", "Information")
    } else {
        [System.Windows.Forms.MessageBox]::Show("Failed to start proxy", "MiMo Proxy", "OK", "Error")
    }
}
