param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('StartBackend', 'StartFrontend', 'Stop')]
    [string]$Action
)
$ErrorActionPreference = 'Stop'
$ProjectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..')).TrimEnd([IO.Path]::DirectorySeparatorChar)
$StateDirectory = Join-Path $ProjectRoot 'backend\data\launcher'
$hash = [Security.Cryptography.SHA256]::Create()
try {
    $ProjectToken = ([BitConverter]::ToString($hash.ComputeHash([Text.Encoding]::UTF8.GetBytes($ProjectRoot.ToLowerInvariant())))).Replace('-', '').Substring(0, 12)
} finally {
    $hash.Dispose()
}

function Get-StateFile([string]$Role) {
    return (Join-Path $StateDirectory ($Role + '.json'))
}

function Get-OwnedProcess([string]$Role) {
    $file = Get-StateFile $Role
    if (-not (Test-Path -LiteralPath $file)) { return $null }
    $state = Get-Content -LiteralPath $file -Raw | ConvertFrom-Json
    if ($state.project -ne $ProjectRoot -or $state.role -ne $Role) {
        throw "Invalid launcher state in $file. Stop servers manually and remove that state file."
    }
    $process = Get-Process -Id ([int]$state.pid) -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        Remove-Item -LiteralPath $file
        return $null
    }
    # PID reuse must never result in stopping a different process.
    if ($process.StartTime.ToUniversalTime().Ticks.ToString() -ne [string]$state.startedTicks) {
        Remove-Item -LiteralPath $file
        Write-Warning "Removed stale $Role state; its PID belongs to another process."
        return $null
    }
    $marker = 'FactAlign_' + $ProjectToken + '_' + $Role
    $details = Get-CimInstance Win32_Process -Filter "ProcessId = $($process.Id)"
    if ($null -eq $details -or -not $details.CommandLine -or $details.CommandLine.IndexOf($marker, [StringComparison]::OrdinalIgnoreCase) -lt 0) {
        throw "Cannot verify ownership of $Role PID $($process.Id). Use Ctrl+C in its terminal."
    }
    return $process
}

try {
    if ($Action -eq 'Stop') {
        $failed = $false
        foreach ($role in @('Backend', 'Frontend')) {
            try {
                $process = Get-OwnedProcess $role
                if ($null -eq $process) {
                    Write-Host "$role is not running under this launcher."
                    continue
                }
                & taskkill.exe /PID $process.Id /T /F | Out-Null
                if ($LASTEXITCODE -ne 0) { throw "Could not stop $role. Use Ctrl+C in its terminal." }
                Remove-Item -LiteralPath (Get-StateFile $role)
                Write-Host "Stopped $role and its child processes."
            } catch {
                Write-Warning $_.Exception.Message
                $failed = $true
            }
        }
        if ($failed) { exit 1 }
        exit 0
    }

    $role = if ($Action -eq 'StartBackend') { 'Backend' } else { 'Frontend' }
    if ($null -ne (Get-OwnedProcess $role)) { throw "$role already has a launcher window. Run stop.bat first." }
    $marker = 'FactAlign_' + $ProjectToken + '_' + $role
    $workingDirectory = $ProjectRoot
    $command = '.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000'
    if ($role -eq 'Frontend') {
        $workingDirectory = Join-Path $ProjectRoot 'frontend'
        $command = 'npm.cmd run dev'
    }
    # The parent cmd stays alive even if a child changes the console title.
    $process = Start-Process -FilePath $env:ComSpec -ArgumentList ('/d /k title ' + $marker + ' & ' + $command) -WorkingDirectory $workingDirectory -WindowStyle Normal -PassThru
    try {
        New-Item -ItemType Directory -Path $StateDirectory -Force | Out-Null
        @{ pid = $process.Id; startedTicks = $process.StartTime.ToUniversalTime().Ticks.ToString(); project = $ProjectRoot; role = $role } |
            ConvertTo-Json | Set-Content -LiteralPath (Get-StateFile $role) -Encoding UTF8
    } catch {
        & taskkill.exe /PID $process.Id /T /F | Out-Null
        throw
    }
    Write-Host "Started $role (PID $($process.Id))."
} catch {
    Write-Error -Message $_.Exception.Message -ErrorAction Continue
    exit 1
}
