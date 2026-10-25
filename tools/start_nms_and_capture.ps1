# One-click flow behind tools\Run-Layout-Capture-0.3.55-cdb-inputs.cmd:
#   - if NMS is not running, start it through Steam and wait for its window;
#   - then arm the one-shot CDB writer capture (-ReadInputs -AutoArm, 30 minutes).
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$SteamExe = 'C:\Program Files (x86)\Steam\steam.exe'
$NmsPath = "G:\SteamLibrary\steamapps\common\No Man's Sky\Binaries\NMS.exe"

function Get-NmsProcess {
    @(Get-CimInstance Win32_Process -Filter "Name='NMS.exe'" | Where-Object {
        $_.ExecutablePath -and ([IO.Path]::GetFullPath($_.ExecutablePath) -ieq [IO.Path]::GetFullPath($NmsPath))
    })
}

if (@(Get-NmsProcess).Count -eq 0) {
    if (-not (Test-Path -LiteralPath $SteamExe)) { throw "Steam not found at $SteamExe" }
    Write-Host 'Starting No Man''s Sky through Steam...' -ForegroundColor Cyan
    Start-Process -FilePath $SteamExe -ArgumentList @('-applaunch', '275850') | Out-Null

    # Wait for the game process and its main window (up to 5 minutes), then let it settle.
    $watch = [Diagnostics.Stopwatch]::StartNew()
    $windowed = $false
    while ($watch.Elapsed.TotalMinutes -lt 5) {
        $nms = @(Get-NmsProcess)
        if ($nms.Count -eq 1) {
            $p = Get-Process -Id $nms[0].ProcessId -ErrorAction SilentlyContinue
            if ($p -and $p.MainWindowHandle -ne [IntPtr]::Zero) { $windowed = $true; break }
        }
        Start-Sleep -Seconds 2
    }
    if (-not $windowed) { throw 'NMS did not open a window within 5 minutes; no capture was armed.' }
    Start-Sleep -Seconds 20
}
else {
    Write-Host 'NMS is already running; arming the capture on it.' -ForegroundColor Cyan
}

Write-Host ''
Write-Host 'Arming the capture now. Load your save if needed and play to the derelict (up to 30 minutes).' -ForegroundColor Green
& (Join-Path $here 'run_layout_capture_0_3_55_cdb.ps1') -ReadInputs -AutoArm -ObservationSeconds 1800
exit $LASTEXITCODE
