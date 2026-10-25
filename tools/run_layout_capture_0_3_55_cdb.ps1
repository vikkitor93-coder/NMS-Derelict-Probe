[CmdletBinding()]
param(
    [ValidateRange(5, 1800)]
    [int]$ObservationSeconds = 30,
    # r3: also let CDB read the 16-byte seed record at R8 and 0x80 bytes of the
    # preset at R9 while the writer is paused. No code runs inside NMS.
    [switch]$ReadInputs,
    # Fewer manual steps: pick the PID when exactly one hash-matched NMS runs, and
    # arm immediately (no Enter prompt). An idle one-shot breakpoint costs nothing.
    [switch]$AutoArm
)

$ErrorActionPreference = 'Stop'
$Profile = if ($ReadInputs) { '0.3.55-cdb-r3-inputs' } else { '0.3.55-cdb-r2' }
$ExpectedNmsSha256 = '13D5060D4EFB9D2A6A6B1B349BC4257231056CC2A055DF4BB15D816262CC3499'
$ExpectedCdbSha256 = '506D1FD7AD306F6F53D8D157375A03A8368446923DEF9457CDFB2E3214054376'
$WriterRva = 0x0039E5E0
$NmsPath = "G:\SteamLibrary\steamapps\common\No Man's Sky\Binaries\NMS.exe"
$CdbPath = 'C:\Program Files (x86)\Windows Kits\10\Debuggers\x64\cdb.exe'
$ModuleName = 'NMS'
$TargetProcessName = 'NMS.exe'
$OutputRoot = if ($ReadInputs) { 'D:\Orca\NMS-Derelict-Probe\live-runtime\NMSDerelictSurveyor\layout-cdb-r3' } else { 'D:\Orca\NMS-Derelict-Probe\live-runtime\NMSDerelictSurveyor\layout-cdb-r2' }
$CaptureScope = if ($ReadInputs) { 'writer entry scalar register and stack arguments, plus debugger reads of the seed record at R8 (0x10 bytes), preset at R9 (0x80 bytes), templates-table header at poi(RCX) (0x30 bytes) and up to 64 RoomTemplates rows (0x2800 bytes); no return value' } else { 'writer entry scalar register and stack arguments only; no pointer dereference; no return value' }
$RunId = [guid]::NewGuid().ToString('N')
$RunRoot = Join-Path $OutputRoot $RunId
$CdbLog = Join-Path $RunRoot 'cdb.log'
$CdbCommands = Join-Path $RunRoot 'cdb-commands.txt'
$StatusPath = Join-Path $RunRoot 'status.json'
# Empty local symbol path: no symbol-server download while the target is frozen.
$SymbolPath = Join-Path $RunRoot 'no-symbols'

function Write-Status {
    param([string]$State, [string]$Detail, [hashtable]$Extra = @{})
    $payload = [ordered]@{
        schema_version = 1
        profile = $Profile
        run_id = $RunId
        state = $State
        detail = $Detail
        utc = [DateTime]::UtcNow.ToString('o')
        target_pid = $script:TargetPid
        target_start_time = $script:TargetStartTime
        target_executable = $NmsPath
        target_executable_sha256 = $ExpectedNmsSha256
        cdb_executable = $CdbPath
        cdb_executable_sha256 = $ExpectedCdbSha256
        writer_rva_hex = ('{0:X8}' -f $WriterRva)
        capture_scope = $CaptureScope
        cdb_log = $CdbLog
    }
    foreach ($key in $Extra.Keys) { $payload[$key] = $Extra[$key] }
    $temporary = $StatusPath + '.tmp'
    $payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $temporary -Encoding UTF8
    # A reader (viewer, antivirus, indexer) holding status.json makes a replace
    # fail transiently; retry so a status write never aborts an armed capture.
    for ($attempt = 1; ; $attempt++) {
        try {
            if (Test-Path -LiteralPath $StatusPath) { [IO.File]::Replace($temporary, $StatusPath, [NullString]::Value) }
            else { [IO.File]::Move($temporary, $StatusPath) }
            return
        }
        catch {
            if ($attempt -ge 40) { throw }
            Start-Sleep -Milliseconds 50
        }
    }
}

function Read-SharedText {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return '' }
    try {
        $stream = [IO.File]::Open($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
        try {
            $reader = [IO.StreamReader]::new($stream)
            try { return $reader.ReadToEnd() }
            finally { $reader.Dispose() }
        }
        finally { $stream.Dispose() }
    }
    catch [IO.IOException] { return '' }
}

function Wait-ForText {
    param([string]$Path, [string]$Needle, [Diagnostics.Process]$Process, [int]$LimitMilliseconds)
    $watch = [Diagnostics.Stopwatch]::StartNew()
    while ($watch.ElapsedMilliseconds -lt $LimitMilliseconds) {
        if ((Read-SharedText $Path) -match ('(?im)^' + [regex]::Escape($Needle) + '\s*$')) { return $true }
        if ($Process.HasExited) { return $false }
        Start-Sleep -Milliseconds 50
    }
    return $false
}

function Get-DqWords([string]$Text, [string]$StartMarker, [string]$EndMarker) {
    # Qwords printed by `dq` between two .echo markers, in memory order.
    $block = [regex]::Match($Text, '(?ims)^' + [regex]::Escape($StartMarker) + '\s*$(.*?)^' + [regex]::Escape($EndMarker) + '\s*$')
    if (-not $block.Success) { return $null }
    $words = [Collections.Generic.List[string]]::new()
    foreach ($line in ($block.Groups[1].Value -split '\r?\n')) {
        $fields = @($line.Trim() -split '\s+' | Where-Object { $_ -match '^[0-9a-f`?]+$' })
        if ($fields.Count -lt 2) { continue }
        foreach ($word in $fields[1..($fields.Count - 1)]) { $words.Add($word.Replace('`','').ToUpperInvariant()) }
    }
    return ,$words.ToArray()
}

function Get-BreakCount([string]$Text) {
    return ([regex]::Matches($Text, 'Break instruction exception - code 80000003')).Count
}

function Send-PromptDetach {
    param([Diagnostics.Process]$Debugger)
    # If a breakpoint command list aborted before its own qd, CDB sits at its
    # prompt with the target stopped; detach from there. Never leave it attached.
    if ($Debugger.HasExited) { return $true }
    try {
        $Debugger.StandardInput.WriteLine('qd')
        $Debugger.StandardInput.Flush()
    }
    catch { return $false }
    return $Debugger.WaitForExit(5000)
}

function Send-TimeoutBreakAndDetach {
    param([Diagnostics.Process]$Debugger, [int]$TargetProcessId, [string]$LogPath)
    # A break-in sent to a target that CDB has already left raises an unhandled
    # int3 and terminates it, so confirm CDB is still attached immediately before.
    if ($Debugger.HasExited) { return 'debugger_already_exited' }
    $before = Get-BreakCount (Read-SharedText $LogPath)
    $handle = [DebugBreakApi]::OpenProcess(0x001F0FFF, $false, $TargetProcessId)
    if ($handle -eq [IntPtr]::Zero) {
        throw "Cannot request the bounded detach break (OpenProcess error $([Runtime.InteropServices.Marshal]::GetLastWin32Error()))."
    }
    try {
        $debuggerPresent = $false
        if (-not [DebugBreakApi]::CheckRemoteDebuggerPresent($handle, [ref]$debuggerPresent)) {
            throw "Cannot confirm debugger attachment (CheckRemoteDebuggerPresent error $([Runtime.InteropServices.Marshal]::GetLastWin32Error())); no break sent."
        }
        if (-not $debuggerPresent -or $Debugger.HasExited) { return 'debugger_already_detached' }
        if ((Read-SharedText $LogPath) -match '(?im)^HIT_WRITER\s*$') { return 'writer_hit_in_progress' }
        if (-not [DebugBreakApi]::DebugBreakProcess($handle)) {
            throw "Cannot request the bounded detach break (DebugBreakProcess error $([Runtime.InteropServices.Marshal]::GetLastWin32Error()))."
        }
    }
    finally { [DebugBreakApi]::CloseHandle($handle) | Out-Null }

    $watch = [Diagnostics.Stopwatch]::StartNew()
    $observed = $false
    while ($watch.ElapsedMilliseconds -lt 5000) {
        if ((Get-BreakCount (Read-SharedText $LogPath)) -gt $before) { $observed = $true; break }
        if ($Debugger.HasExited) { break }
        Start-Sleep -Milliseconds 50
    }
    if (-not $observed) { throw 'CDB did not report the timeout break; target state needs manual review.' }
    $Debugger.StandardInput.WriteLine('qd')
    $Debugger.StandardInput.Flush()
    if (-not $Debugger.WaitForExit(5000)) { throw 'CDB did not detach within five seconds after the timeout break.' }
    return 'timeout_break_detached'
}

$script:TargetPid = $null
$script:TargetStartTime = $null
$script:ModuleBase = $null
$script:ExpectedWriterAddress = $null
$script:BreakpointAddress = $null
$script:PromptDetachUsed = $false
$script:Debugger = $null
$script:Armed = $false
$script:Attached = $false
$script:FinalStateWritten = $false

try {
    Write-Host "NMS layout writer scalar observer $Profile" -ForegroundColor Cyan
    Write-Host 'This attaches a one-shot CDB breakpoint to an already-running NMS process. It does not launch NMS or load Python hooks.'
    if ($ReadInputs) { Write-Host 'It records six scalar arguments at writer entry and has CDB read the seed record (R8) and preset (R9); it captures no return value.' }
    else { Write-Host 'It records six scalar arguments at writer entry, reads no pointed memory, and captures no return value.' }
    Write-Host ''

    if (-not (Test-Path -LiteralPath $NmsPath)) { throw "Expected NMS executable not found: $NmsPath" }
    if (-not (Test-Path -LiteralPath $CdbPath)) { throw "CDB not found: $CdbPath" }
    $nmsHash = (Get-FileHash -LiteralPath $NmsPath -Algorithm SHA256).Hash
    if ($nmsHash -ne $ExpectedNmsSha256) { throw "NMS SHA-256 mismatch. Expected $ExpectedNmsSha256; found $nmsHash. No attach attempted." }
    $cdbHash = (Get-FileHash -LiteralPath $CdbPath -Algorithm SHA256).Hash
    if ($cdbHash -ne $ExpectedCdbSha256) { throw "CDB SHA-256 mismatch. Expected $ExpectedCdbSha256; found $cdbHash. No attach attempted." }

    $nmsProcesses = @(Get-CimInstance Win32_Process -Filter ("Name='{0}'" -f $TargetProcessName) | Where-Object { $_.ExecutablePath -and ([IO.Path]::GetFullPath($_.ExecutablePath) -ieq [IO.Path]::GetFullPath($NmsPath)) })
    if ($nmsProcesses.Count -eq 0) { throw 'No running NMS process was found at the hash-matched executable path. Start NMS normally and load the intended save first.' }
    Write-Host 'Hash-matched NMS process(es):' -ForegroundColor Yellow
    foreach ($candidate in $nmsProcesses) {
        $candidateProcess = Get-Process -Id $candidate.ProcessId
        Write-Host ("  PID {0}  started {1:yyyy-MM-dd HH:mm:ss}  {2}" -f $candidate.ProcessId, $candidateProcess.StartTime, $candidate.ExecutablePath)
    }
    $pidText = if ($AutoArm -and $nmsProcesses.Count -eq 1) { [string]$nmsProcesses[0].ProcessId } else { Read-Host 'Enter the PID for the intended NMS session' }
    $selected = @($nmsProcesses | Where-Object { $_.ProcessId.ToString() -eq $pidText.Trim() })
    if ($selected.Count -ne 1) { throw 'The entered PID was not in the hash-matched NMS list. No attach attempted.' }
    $script:TargetPid = [int]$selected[0].ProcessId
    $targetProcess = Get-Process -Id $script:TargetPid
    $script:TargetStartTime = $targetProcess.StartTime.ToUniversalTime().ToString('o')
    try { $script:ModuleBase = [UInt64]$targetProcess.MainModule.BaseAddress.ToInt64() }
    catch { throw "Cannot read the target's main-module base address ($($_.Exception.Message)). No attach attempted." }
    $script:ExpectedWriterAddress = $script:ModuleBase + [UInt64]$WriterRva

    Write-Host ''
    Write-Host 'Before arming: have the intended save loaded, stand at the derelict approach, and stop before the generation trigger.' -ForegroundColor Yellow
    Write-Host ("The observer waits {0} seconds. After ARMED appears, perform the short approach that normally triggers the ship/layout generation." -f $ObservationSeconds)
    Write-Host 'A breakpoint briefly pauses NMS once. On timeout, the controller requests a break and detaches. No memory dump or Python callback is used.'
    if (-not $AutoArm) { $null = Read-Host 'Press Enter when ready to arm the observer' }

    $currentTarget = Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f $script:TargetPid)
    $currentProcess = Get-Process -Id $script:TargetPid -ErrorAction SilentlyContinue
    if (-not $currentTarget -or -not $currentProcess -or
        [IO.Path]::GetFullPath($currentTarget.ExecutablePath) -ine [IO.Path]::GetFullPath($NmsPath) -or
        $currentProcess.StartTime.ToUniversalTime().ToString('o') -ne $script:TargetStartTime) {
        throw 'The selected NMS process changed while waiting for input. No attach attempted.'
    }

    New-Item -ItemType Directory -Path $RunRoot -Force | Out-Null
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class DebugBreakApi {
    [DllImport("kernel32.dll", SetLastError=true)] public static extern IntPtr OpenProcess(uint access, bool inherit, int processId);
    [DllImport("kernel32.dll", SetLastError=true)] public static extern bool DebugBreakProcess(IntPtr process);
    [DllImport("kernel32.dll", SetLastError=true)] public static extern bool CheckRemoteDebuggerPresent(IntPtr process, ref bool present);
    [DllImport("kernel32.dll", SetLastError=true)] public static extern bool CloseHandle(IntPtr handle);
}
'@
    New-Item -ItemType Directory -Path $SymbolPath -Force | Out-Null
    # bl prints the nearest export name (NMS exports AK::* symbols below the
    # writer), so the resolved address is verified numerically, not by name.
    # Source-map rows (FUN_14039EC00 output) live in the writer's global: count at
    # [RCX+0x24], array at [RCX+0x28], 0x2B0-byte rows, source descriptor pointer at
    # row+0x2A0. Raw rows go to a file via .writemem; descriptors are dumped as text.
    # Both are capped at 0x1000 rows and every pointer chase is .catch-guarded.
    # CDB treats backslashes in a bp command string as escapes, so pass the path with
    # forward slashes; and use two plain .if checks, since .if/.else aborted the list.
    $SourceRowsFile = Join-Path $RunRoot 'source-rows.bin'
    $sourceRowsCdbPath = $SourceRowsFile.Replace('\', '/')
    $sourceRowCommands = '.catch { dq @rcx L6 }; .echo SOURCE_HEADER_END; ' +
        '.catch { .if (dwo(@rcx+0x24) <= 0x1000) { .writemem ' + $sourceRowsCdbPath + ' poi(@rcx+0x28) L?(dwo(@rcx+0x24)*0x2b0) } }; ' +
        '.catch { .if (dwo(@rcx+0x24) > 0x1000) { .echo SOURCE_ROWS_OVER_CAP } }; .echo SOURCE_ROWS_WRITTEN; ' +
        # The per-row descriptor text loop paused NMS ~25 s for 1,876 rows (run 98a782a5…,
        # which captured them all); it is disabled so future pauses stay sub-second.
        '.echo SOURCE_DESCRIPTORS_END; '
    $commandLines = @(
        ('.printf "BP_ADDRESS=%p\n", {0}+0x{1:X8}' -f $ModuleName, $WriterRva),
        ('.printf "MODULE_BASE=%p\n", {0}' -f $ModuleName),
        ('bp {0}+0x{1:X8} ".echo HIT_WRITER; r rcx; r rdx; r r8; r r9; .echo REGISTERS_CAPTURED; dq @rsp+0x28 L2; .echo STACK_CAPTURED; {2}qd"' -f $ModuleName, $WriterRva, $(if ($ReadInputs) { 'dq @r8 L2; .echo SEED_RECORD_END; dq @r9 L10; .echo PRESET_RECORD_END; .catch { dq poi(@rcx) L6 }; .echo TABLE_HEADER_END; .catch { dq poi(poi(@rcx)+0x20) L500 }; .echo TABLE_ROWS_END; ' + $sourceRowCommands } else { '' })),
        'bl',
        '.echo ARMED_WRITER',
        'g'
    )
    [IO.File]::WriteAllLines($CdbCommands, $commandLines, [Text.Encoding]::ASCII)

    $startInfo = [Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $CdbPath
    $startInfo.Arguments = '-logo "' + $CdbLog + '" -y "' + $SymbolPath + '" -p ' + $script:TargetPid + ' -cf "' + $CdbCommands + '"'
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardInput = $true
    $script:Debugger = [Diagnostics.Process]::Start($startInfo)
    Write-Status -State 'attaching' -Detail 'CDB started; waiting for breakpoint registration and ARMED confirmation.'

    if (-not (Wait-ForText $CdbLog 'ARMED_WRITER' $script:Debugger 10000)) {
        if ($script:Debugger.HasExited) { throw 'CDB exited before reporting ARMED. No capture was attempted.' }
        $script:Attached = (Get-BreakCount (Read-SharedText $CdbLog)) -gt 0
        throw 'CDB did not report ARMED within ten seconds. The target may still be under debugger control; timeout detach will be attempted.'
    }
    $script:Armed = $true
    $script:Attached = $true
    $logSoFar = Read-SharedText $CdbLog
    $expectedHex = '{0:X16}' -f $script:ExpectedWriterAddress
    $cdbBpAddress = [regex]::Match($logSoFar, '(?im)^BP_ADDRESS=([0-9a-f`]+)\s*$')
    $cdbModuleBase = [regex]::Match($logSoFar, '(?im)^MODULE_BASE=([0-9a-f`]+)\s*$')
    $bpLine = [regex]::Match($logSoFar, '(?im)^\s*0\s+e\s+([0-9a-f`]+)\s+0001\s+\(0001\)')
    $script:BreakpointAddress = if ($bpLine.Success) { $bpLine.Groups[1].Value.Replace('`','').ToUpperInvariant().PadLeft(16, '0') } else { $null }
    if (-not $cdbBpAddress.Success -or -not $cdbModuleBase.Success -or -not $bpLine.Success -or
        $cdbBpAddress.Groups[1].Value.Replace('`','').ToUpperInvariant().PadLeft(16, '0') -ne $expectedHex -or
        $cdbModuleBase.Groups[1].Value.Replace('`','').ToUpperInvariant().PadLeft(16, '0') -ne ('{0:X16}' -f $script:ModuleBase) -or
        $script:BreakpointAddress -ne $expectedHex) {
        throw ("CDB did not confirm the writer breakpoint at module base + RVA (expected {0}, breakpoint {1})." -f $expectedHex, $script:BreakpointAddress)
    }
    Write-Status -State 'armed' -Detail ("One-shot writer breakpoint armed for {0} seconds; NMS has resumed." -f $ObservationSeconds)
    Write-Host ''
    Write-Host ("ARMED: one-shot writer breakpoint active for {0} seconds. NMS resumed; continue with the derelict approach now." -f $ObservationSeconds) -ForegroundColor Green

    $deadline = [Diagnostics.Stopwatch]::StartNew()
    $eventHit = $false
    while ($deadline.Elapsed.TotalSeconds -lt $ObservationSeconds) {
        $currentText = Read-SharedText $CdbLog
        if ($currentText -match '(?im)^HIT_WRITER\s*$') { $eventHit = $true; break }
        if ($script:Debugger.HasExited) { break }
        Start-Sleep -Milliseconds 50
    }

    $timeoutOutcome = $null
    if (-not $eventHit -and -not $script:Debugger.HasExited) {
        $timeoutOutcome = Send-TimeoutBreakAndDetach -Debugger $script:Debugger -TargetProcessId $script:TargetPid -LogPath $CdbLog
    }
    if (-not $eventHit -and (Read-SharedText $CdbLog) -match '(?im)^HIT_WRITER\s*$') {
        # The writer hit raced the deadline; its own one-shot qd owns the detach.
        $eventHit = $true
    }

    if ($eventHit) {
        $script:PromptDetachUsed = $false
        if (-not $script:Debugger.HasExited -and -not $script:Debugger.WaitForExit(5000)) {
            $script:PromptDetachUsed = $true
            if (-not (Send-PromptDetach $script:Debugger)) {
                throw 'Writer breakpoint hit, its one-shot detach did not run, and the prompt qd fallback did not detach CDB within five seconds.'
            }
        }
        $fullText = Read-SharedText $CdbLog
        $hitMatch = [regex]::Match($fullText, '(?im)^HIT_WRITER\s*$')
        $text = $fullText.Substring($hitMatch.Index)
        if ($text -notmatch '(?im)^REGISTERS_CAPTURED\s*$' -or $text -notmatch '(?im)^STACK_CAPTURED\s*$') {
            throw 'Writer breakpoint hit, but the expected scalar arguments were not fully logged.'
        }
        $rvaArgs = @{}
        foreach ($pair in @(
            @('rcx_global_table', '(?im)^rcx=([0-9a-f`]+)'),
            @('rdx_param2_raw', '(?im)^rdx=([0-9a-f`]+)'),
            @('r8_seed_pointer', '(?im)^r8=([0-9a-f`]+)'),
            @('r9_preset_pointer', '(?im)^r9=([0-9a-f`]+)')
        )) {
            $match = [regex]::Match($text, $pair[1])
            if (-not $match.Success) { throw "CDB output did not contain $($pair[0])." }
            $rvaArgs[$pair[0]] = $match.Groups[1].Value.Replace('`','').ToUpperInvariant()
        }
        $stackMatch = [regex]::Match($text, '(?im)^([0-9a-f`]+)\s+([0-9a-f`]+)\s+([0-9a-f`]+)\s*\r?\nSTACK_CAPTURED')
        if (-not $stackMatch.Success) { throw 'CDB output did not contain both stack arguments.' }
        $rvaArgs['stack_arg5_raw'] = $stackMatch.Groups[2].Value.Replace('`','').ToUpperInvariant()
        $rvaArgs['stack_arg6_raw'] = $stackMatch.Groups[3].Value.Replace('`','').ToUpperInvariant()
        $inputs = $null
        if ($ReadInputs) {
            $seedWords = Get-DqWords $text 'STACK_CAPTURED' 'SEED_RECORD_END'
            $presetWords = Get-DqWords $text 'SEED_RECORD_END' 'PRESET_RECORD_END'
            $inputs = [ordered]@{
                seed_record_qwords = $seedWords
                seed_record_readable = [bool]($seedWords -and $seedWords.Count -eq 2 -and -not ($seedWords -match '\?'))
                preset_record_qwords = $presetWords
                preset_record_readable = [bool]($presetWords -and $presetWords.Count -eq 16 -and -not ($presetWords -match '\?'))
            }
            # RCX = &global slot holding the loaded GcGeneratedBaseTemplatesTable;
            # RoomTemplates pointer at +0x20, count at +0x28, rows of 0xA0 bytes (<= 64 read).
            $headerWords = Get-DqWords $text 'PRESET_RECORD_END' 'TABLE_HEADER_END'
            $rowWords = Get-DqWords $text 'TABLE_HEADER_END' 'TABLE_ROWS_END'
            $inputs['templates_table_header_qwords'] = $headerWords
            $inputs['templates_table_header_readable'] = [bool]($headerWords -and $headerWords.Count -eq 6 -and -not ($headerWords -match '\?'))
            if ($inputs.templates_table_header_readable) {
                $rowCount = [Convert]::ToUInt32($headerWords[5].Substring(8, 8), 16)
                $inputs['templates_row_pointer'] = $headerWords[4]
                $inputs['templates_row_count'] = $rowCount
                $rows = [Collections.Generic.List[string]]::new()
                $availableRows = if ($rowWords) { [int][Math]::Floor($rowWords.Count / 20) } else { 0 }
                $limit = 64
                if ([double]$rowCount -lt $limit) { $limit = [int]$rowCount }
                if ($availableRows -lt $limit) { $limit = $availableRows }
                for ($r = 0; $r -lt $limit; $r++) { $rows.Add(($rowWords[($r * 20)..($r * 20 + 19)] -join ' ')) }
                $inputs['templates_rows_qwords'] = $rows.ToArray()
                $inputs['templates_rows_readable'] = [bool]($rows.Count -gt 0 -and -not ($rows -match '\?'))
                $inputs['templates_rows_truncated'] = [bool]($rowCount -gt $rows.Count)
            }
            $sourceHeader = Get-DqWords $text 'TABLE_ROWS_END' 'SOURCE_HEADER_END'
            $inputs['source_global_qwords'] = $sourceHeader
            $inputs['source_global_readable'] = [bool]($sourceHeader -and $sourceHeader.Count -eq 6 -and -not ($sourceHeader -match '\?'))
            if ($inputs.source_global_readable) {
                $inputs['source_row_count'] = [Convert]::ToUInt32($sourceHeader[4].Substring(0, 8), 16)
                $inputs['source_row_pointer'] = $sourceHeader[5]
            }
            $inputs['source_rows_over_cap'] = [bool]($text -match '(?im)^SOURCE_ROWS_OVER_CAP\s*$')
            if (Test-Path -LiteralPath $SourceRowsFile) {
                $rowsItem = Get-Item -LiteralPath $SourceRowsFile
                $inputs['source_rows_file'] = $SourceRowsFile
                $inputs['source_rows_bytes'] = $rowsItem.Length
                $inputs['source_rows_sha256'] = (Get-FileHash -LiteralPath $SourceRowsFile -Algorithm SHA256).Hash
                $inputs['source_rows_whole'] = [bool]($rowsItem.Length -gt 0 -and $rowsItem.Length % 0x2B0 -eq 0)
            }
            $descriptorWords = Get-DqWords $text 'SOURCE_ROWS_WRITTEN' 'SOURCE_DESCRIPTORS_END'
            $descriptors = [Collections.Generic.List[string]]::new()
            if ($descriptorWords) {
                for ($d = 0; $d + 16 -le $descriptorWords.Count; $d += 16) { $descriptors.Add(($descriptorWords[$d..($d + 15)] -join ' ')) }
            }
            $inputs['source_descriptors_qwords'] = $descriptors.ToArray()
            if ($inputs.seed_record_readable) {
                # Writer reads qword seed at +0 and a "seed present" byte at +8.
                $inputs['seed_value'] = $seedWords[0]
                $inputs['seed_present_byte'] = $seedWords[1].Substring(14, 2)
            }
        }
        $afterDetach = Get-Process -Id $script:TargetPid -ErrorAction SilentlyContinue
        $sameTargetAlive = [bool]($afterDetach -and $afterDetach.StartTime.ToUniversalTime().ToString('o') -eq $script:TargetStartTime)
        $detail = @{
            breakpoint_address = $script:BreakpointAddress
            module_base = ('{0:X16}' -f $script:ModuleBase)
            writer_arguments = $rvaArgs
            writer_return_captured = $false
            detach_via_prompt_fallback = $script:PromptDetachUsed
            writer_inputs = $inputs
            target_alive_after_detach = $sameTargetAlive
        }
        Write-Status -State 'capture_persisted' -Detail 'One writer call captured at entry; CDB detached from the one-shot command.' -Extra $detail
        $script:FinalStateWritten = $true
        Write-Host ''
        Write-Host 'CAPTURED: one writer call recorded. CDB detached. The six values are raw scalars; pointer values were not read.' -ForegroundColor Green
        Write-Host ("Evidence: {0}" -f $StatusPath)
        Write-Host ("Raw CDB log: {0}" -f $CdbLog)
    }
    elseif ($timeoutOutcome -ne 'timeout_break_detached') {
        throw ("CDB left the target before a writer breakpoint hit ({0}). See cdb.log; no successful capture is claimed." -f $(if ($timeoutOutcome) { $timeoutOutcome } else { 'debugger_exited' }))
    }
    else {
        $sameProcess = Get-Process -Id $script:TargetPid -ErrorAction SilentlyContinue
        if (-not $sameProcess -or $sameProcess.StartTime.ToUniversalTime().ToString('o') -ne $script:TargetStartTime) {
            throw 'CDB detached, but the original NMS process identity could not be confirmed afterward.'
        }
        Write-Status -State 'timeout_no_writer_event' -Detail 'No writer breakpoint in the observation window; controller break was observed, CDB detached, and the same NMS process remained alive.' -Extra @{ target_alive_after_detach = $true; observation_seconds = $ObservationSeconds }
        $script:FinalStateWritten = $true
        Write-Host ''
        Write-Host "TIMED OUT: no writer call in $ObservationSeconds seconds. CDB detached and the same NMS process is still running." -ForegroundColor Yellow
        Write-Host 'Do not repeat the approach for this capture. Close NMS normally when ready; the status records that no event was captured.'
        Write-Host ("Evidence: {0}" -f $StatusPath)
    }
}
catch {
    $message = $_.Exception.Message
    if ($script:Debugger -and -not $script:Debugger.HasExited -and ($script:Armed -or $script:Attached)) {
        try {
            $recovery = Send-TimeoutBreakAndDetach -Debugger $script:Debugger -TargetProcessId $script:TargetPid -LogPath $CdbLog
            # A logged hit whose command list never reached qd leaves the target stopped at the prompt.
            if ($recovery -eq 'writer_hit_in_progress' -and -not (Send-PromptDetach $script:Debugger)) {
                $message += ' Prompt qd fallback did not detach CDB; target state needs manual review.'
            }
        } catch { $message += ' Detach recovery also needs review: ' + $_.Exception.Message }
    }
    if ($RunRoot -and (Test-Path -LiteralPath $RunRoot) -and -not $script:FinalStateWritten) {
        try { Write-Status -State 'error_review_required' -Detail $message -Extra @{ target_process_rechecked = [bool](Get-Process -Id $script:TargetPid -ErrorAction SilentlyContinue) } } catch { }
    }
    Write-Host ''
    Write-Host ("STOP: {0}" -f $message) -ForegroundColor Red
    if ($RunRoot -and (Test-Path -LiteralPath $RunRoot)) { Write-Host ("Review status/logs under {0}" -f $RunRoot) }
    exit 2
}
finally {
    if ($script:Debugger) { $script:Debugger.Dispose() }
}

Write-Host ''
exit 0
