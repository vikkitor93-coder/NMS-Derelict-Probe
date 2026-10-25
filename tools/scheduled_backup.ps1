# Scheduled every 30 minutes by the "NMS-Derelict-Research-Backup" task.
# 1. Full local snapshot ZIP of the working tree to D:\Orca\NMS-Derelict-Probe-backups
#    (skipped when nothing changed; newest 48 kept = 24 hours).
# 2. Snapshot the out-of-tree end-reward and crate-loot caches to the same D: backup root; newest 48 of each kept.
# Snapshot only. Publishing and repository commits are separate user-controlled actions.
$ErrorActionPreference = 'Stop'
$repo = 'D:\Orca\NMS-Derelict-Probe'
$backupRoot = 'D:\Orca\NMS-Derelict-Probe-backups'
$rewardCache = 'D:\Orca\NMS-Derelict-Probe-analysis\end-reward-cache\rewards.csv'
$crateLootCache = 'D:\Orca\NMS-Derelict-Probe-analysis\crate-loot-cache\predictions-v2.csv'
$python = Join-Path $env:USERPROFILE 'AppData\Local\Programs\Python\Python313\python.exe'
$log = Join-Path $backupRoot 'backup-research.log'
New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null

function Write-Log([string]$Message) {
  Add-Content -LiteralPath $log -Value "[$([DateTime]::UtcNow.ToString('o'))] $Message"
}

function Invoke-Native([string]$Exe, [string[]]$NativeArgs) {
  # PowerShell 5.1 can turn harmless native stderr into terminating errors when
  # ErrorActionPreference is Stop; capture both streams and trust the exit code.
  $priorPreference = $ErrorActionPreference
  try {
    $ErrorActionPreference = 'Continue'
    $output = & $Exe @NativeArgs 2>&1
    $code = $LASTEXITCODE
  } finally {
    $ErrorActionPreference = $priorPreference
  }
  if ($output) { $output | ForEach-Object { Add-Content -LiteralPath $log -Value "  $_" } }
  return $code
}

$failed = $false
Write-Log 'Backup started'

try {
  $code = Invoke-Native $python @('-I', (Join-Path $repo 'tools\build_project_snapshot_zip.py'), '--label', 'auto', '--out-dir', $backupRoot, '--skip-unchanged', '--keep', '48')
  if ($code -ne 0) { throw "snapshot builder failed with exit $code" }
  Write-Log 'Snapshot step finished'
} catch {
  Write-Log "ERROR (snapshot): $_"
  $failed = $true
}

try {
  if (Test-Path -LiteralPath $rewardCache -PathType Leaf) {
    $cacheBackupRoot = Join-Path $backupRoot 'end-reward-cache'
    New-Item -ItemType Directory -Path $cacheBackupRoot -Force | Out-Null
    $stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
    $cacheBackup = Join-Path $cacheBackupRoot "rewards-$stamp.csv"
    Copy-Item -LiteralPath $rewardCache -Destination $cacheBackup
    $copies = Get-ChildItem -LiteralPath $cacheBackupRoot -Filter 'rewards-*.csv' -File |
      Sort-Object LastWriteTimeUtc -Descending
    $copies | Select-Object -Skip 48 | Remove-Item -Force
    $length = (Get-Item -LiteralPath $cacheBackup).Length
    Write-Log "Reward cache snapshot: $cacheBackup ($length bytes)"
  } else {
    Write-Log 'Reward cache snapshot skipped: cache does not exist yet'
  }
} catch {
  Write-Log "ERROR (reward cache snapshot): $_"
  $failed = $true
}

try {
  if (Test-Path -LiteralPath $crateLootCache -PathType Leaf) {
    $cacheBackupRoot = Join-Path $backupRoot 'crate-loot-cache'
    New-Item -ItemType Directory -Path $cacheBackupRoot -Force | Out-Null
    $stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
    $cacheBackup = Join-Path $cacheBackupRoot "predictions-v2-$stamp.csv"
    Copy-Item -LiteralPath $crateLootCache -Destination $cacheBackup
    $copies = Get-ChildItem -LiteralPath $cacheBackupRoot -Filter 'predictions-v2-*.csv' -File |
      Sort-Object LastWriteTimeUtc -Descending
    $copies | Select-Object -Skip 48 | Remove-Item -Force
    $length = (Get-Item -LiteralPath $cacheBackup).Length
    Write-Log "Crate-loot cache snapshot: $cacheBackup ($length bytes)"
  } else {
    Write-Log 'Crate-loot cache snapshot skipped: cache does not exist yet'
  }
} catch {
  Write-Log "ERROR (crate-loot cache snapshot): $_"
  $failed = $true
}

if ($failed) { exit 1 }
exit 0
