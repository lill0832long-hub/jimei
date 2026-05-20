$scriptPath = "C:\Users\Administrator\AppData\Roaming\npm\node_modules\mimo2codex\dist\cli.js"

$running = Get-CimInstance Win32_Process -Filter "Name='node.exe'" | Where-Object { $_.CommandLine -like "*mimo2codex*" }

if ($running) {
    $running | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
} else {
    Start-Process -FilePath "node" -ArgumentList "`"$scriptPath`" --no-admin --no-update-check" -NoNewWindow
}
