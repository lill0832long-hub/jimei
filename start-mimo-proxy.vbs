Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "powershell.exe -ExecutionPolicy Bypass -File ""e:\ClaudeCode\my-project\start-mimo-proxy.ps1""", 0, False
