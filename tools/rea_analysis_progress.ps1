# Progress report for the one-time REA/Ghidra full analysis of NMS.exe.
# Ghidra headless exposes no true percentage, so this reports the phase plus
# activity indicators. Run: powershell -NoProfile -File tools\rea_analysis_progress.ps1
$ErrorActionPreference = 'SilentlyContinue'
$runDir = 'D:\Orca\NMS-Derelict-Probe-analysis\rea'
$marker = @(Get-Content (Join-Path $runDir 'run-started.txt'))
$started = [datetime]::Parse($marker[0]).ToUniversalTime()
$now = [datetime]::UtcNow
$elapsed = $now - $started
$runtime = Get-ChildItem 'D:\Orca\Temp' -Directory -Filter 'rea-ghidra-*' | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
$log = if ($runtime) { Join-Path $runtime.FullName 'ghidra.log' }
$text = if ($log -and (Test-Path $log)) { Get-Content $log -Raw } else { '' }

$phase = 'starting'
if ($text -match 'IMPORTING:') { $phase = 'importing NMS.exe' }
if ($text -match 'ANALYZING all memory and code') { $phase = 'auto-analysis (longest phase)' }
if ($text -match '(?i)Analysis succeeded|Total Time') { $phase = 'analysis finished; REA preparing results' }
$result = Join-Path $runDir 'fn-1403a4400.json'
if ($marker.Count -ge 2 -and $marker[1] -match 'exit=(\d+)') {
    $phase = if ($Matches[1] -eq '0') { 'DONE (snapshot written)' } else { "STOPPED with exit $($Matches[1]); see fn-1403a4400.json" }
}

$jvm = Get-CimInstance Win32_Process -Filter "Name='java.exe'" | Where-Object { $_.CommandLine -match 'ghidra' } | Select-Object -First 1
$jvmLine = 'no Ghidra JVM running'
if ($jvm) {
    $p = Get-Process -Id $jvm.ProcessId
    $cores = if ($elapsed.TotalSeconds -gt 0) { $p.CPU / $elapsed.TotalSeconds } else { 0 }
    $jvmLine = 'JVM {0}: {1:N1} GB RAM, {2:N0} CPU-s (~{3:N1} cores busy on average)' -f $jvm.ProcessId, ($p.WorkingSet64 / 1GB), $p.CPU, $cores
}
$projectBytes = if ($runtime) { (Get-ChildItem $runtime.FullName -Recurse -File | Measure-Object Length -Sum).Sum } else { 0 }
# The current analyzer comes from a JVM thread dump of the main thread (cheap, read-only).
$analyzer = $null
if ($jvm) {
    $jstack = 'D:\Orca\Tools\jdk-25.0.4.1+1\bin\jstack.exe'
    $dump = & $jstack $jvm.ProcessId 2>$null | Out-String
    $m = [regex]::Match($dump, '(?s)"main".*?at ghidra\.app\.plugin\.core\.\S*?\.(\w+Analyzer)\.')
    if ($m.Success) { $analyzer = $m.Groups[1].Value }
}
$lastLine = ($text -split "`r?`n" | Where-Object { $_ -match '^\d{4}-\d\d-\d\d' } | Select-Object -Last 1)

Write-Host ('REA/Ghidra analysis of NMS.exe  [{0:yyyy-MM-dd HH:mm} UTC]' -f $now) -ForegroundColor Cyan
Write-Host ('Phase:    {0}' -f $phase)
Write-Host ('Elapsed:  {0:%h}h {0:mm}m (started {1:HH:mm} UTC; REA limit 8h)' -f $elapsed, $started)
Write-Host ('Activity: {0}' -f $jvmLine)
Write-Host ('Project:  {0:N2} GB on disk (grows during analysis)' -f ($projectBytes / 1GB))
if ($analyzer) { Write-Host ('Analyzer: {0} (current Ghidra analysis pass)' -f $analyzer) }
if ($lastLine) { Write-Host ('Last log: {0}' -f ($lastLine.Substring(0, [Math]::Min(160, $lastLine.Length)))) }
