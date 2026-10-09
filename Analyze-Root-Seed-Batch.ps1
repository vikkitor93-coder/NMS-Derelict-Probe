$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$dataRoot = Join-Path $env:LOCALAPPDATA 'NMSDerelictSurveyor'
$out = Join-Path $dataRoot 'asset-work-v1\root-seed-batch-latest.json'
$pythonFile = Join-Path $dataRoot 'python-executable.txt'
$python = if (Test-Path $pythonFile) { (Get-Content -Raw $pythonFile).Trim() } else { 'python' }
if (-not $python) { $python = 'python' }

Write-Host 'NMS Derelict Surveyor - multi-system root seed correlation' -ForegroundColor Cyan
$script = Join-Path $root 'tools\analyze_root_seed_batch.py'
if (-not (Test-Path $script)) { throw "Missing analyzer: $script" }
& $python $script --root $dataRoot --out $out
if ($LASTEXITCODE -ne 0) { throw 'Root-seed batch analysis failed.' }
Write-Host 'The analysis reports correlations only; it does not claim a seed derivation.' -ForegroundColor Yellow
