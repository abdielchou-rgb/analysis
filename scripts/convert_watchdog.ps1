# Watchdog: ensure batch_convert_resumable.py is running; restart if dead.
$running = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*batch_convert_resumable*' }

if (-not $running) {
    $log = "D:\Claude\projects\2hao-analyst\benchmark\golden\watchdog.log"
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    try {
        Start-Process -FilePath "D:\Claude\pro-stack\.venv\Scripts\python.exe" `
            -ArgumentList "D:\Claude\projects\2hao-analyst\scripts\batch_convert_resumable.py" `
            -WorkingDirectory "D:\Claude\projects\2hao-analyst" `
            -WindowStyle Hidden
        Add-Content -Path $log -Value "[$ts] restarted conversion process"
    } catch {
        Add-Content -Path $log -Value "[$ts] FAILED to restart: $_"
    }
}
