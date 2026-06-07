<#
.SYNOPSIS
    BOYSER AI — Installer for Windows (PowerShell)
.DESCRIPTION
    Run via:
        iex ((New-Object System.Net.WebClient).DownloadString('https://raw.githubusercontent.com/nanofatdog/boyser-ai/main/install.ps1'))
    Or run .\install.ps1 if cloned
.NOTES
    Requires: Python 3.10+, Git for Windows (recommended)
#>

$ErrorActionPreference = "Stop"
$Host.UI.RawUI.WindowTitle = "BOYSER AI Installer"

Write-Host ""
Write-Host "  ✻ BOYSER AI" -ForegroundColor Cyan
Write-Host "  ───────────────────────────────" -ForegroundColor Cyan
Write-Host "  CLI coding agent สไตล์ Claude Code" -ForegroundColor Cyan
Write-Host ""

# ---- Check Python ----
try {
    $py = (Get-Command python -ErrorAction Stop).Source
    $ver = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    if ([version]$ver -lt [version]"3.10") {
        throw "Python 3.10+ required, found $ver"
    }
    Write-Host "  ✓ Python $ver at $py" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Python 3.10+ required. Download from: https://python.org (tick 'Add to PATH')" -ForegroundColor Red
    exit 1
}

# ---- Determine install dir ----
$installDir = "$env:USERPROFILE\.local\share\boyser-ai"
$scriptPath = $MyInvocation.MyCommand.Path

if ($scriptPath -eq "" -or $scriptPath -eq $null -or $scriptPath -notlike "*.ps1") {
    # Running from web download
    Write-Host "  → Installing to $installDir" -ForegroundColor Yellow
    if (Test-Path $installDir) {
        Write-Host "  → Updating existing installation..."
        Push-Location $installDir
        & git pull --ff-only 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  ⚠ git pull failed, re-cloning..." -ForegroundColor Yellow
            Pop-Location
            Remove-Item -Recurse -Force $installDir -ErrorAction SilentlyContinue
            & git clone --depth 1 https://github.com/nanofatdog/boyser-ai.git $installDir
        } else {
            Pop-Location
        }
    } else {
        Write-Host "  → Cloning repository..."
        New-Item -ItemType Directory -Path (Split-Path $installDir -Parent) -Force | Out-Null
        & git clone --depth 1 https://github.com/nanofatdog/boyser-ai.git $installDir
    }
    $DIR = $installDir
} else {
    # Running from local script
    $DIR = Split-Path -Parent $scriptPath
    Write-Host "  → Installing from $DIR" -ForegroundColor Yellow
}
Set-Location $DIR

# ---- Create virtual environment ----
Write-Host "`n  → Setting up virtual environment..." -ForegroundColor Yellow
$venv = "$DIR\.venv"
if (-not (Test-Path $venv)) {
    & python -m venv $venv
}
$pip = "$venv\Scripts\pip.exe"
& $pip install --upgrade pip -q

# ---- Install dependencies ----
Write-Host "  → Installing dependencies..." -ForegroundColor Yellow
& $pip install -r "$DIR\requirements.txt" -q

# ---- Install skills ----
Write-Host "  → Installing skills..." -ForegroundColor Yellow
$skillDir = "$env:USERPROFILE\.config\boyser-ai\skills"
New-Item -ItemType Directory -Path $skillDir -Force | Out-Null
$count = 0
foreach ($s in Get-ChildItem "$DIR\skills\*" -Directory) {
    $target = "$skillDir\$($s.Name)"
    if (-not (Test-Path $target)) {
        Copy-Item -Recurse $s.FullName $target
        $count++
    }
}
Write-Host "     $count skills installed (skipped existing)" -ForegroundColor Gray

# ---- Create launcher ----
Write-Host "  → Creating launcher..." -ForegroundColor Yellow
$binDir = "$env:USERPROFILE\.local\bin"
New-Item -ItemType Directory -Path $binDir -Force | Out-Null

$launcher = "$binDir\boyser-ai.cmd"
@"
@echo off
"$venv\Scripts\python.exe" "$DIR\agent.py" %*
"@ | Out-File -FilePath $launcher -Encoding ASCII

# ---- Add to PATH ----
$path = [Environment]::GetEnvironmentVariable("Path", "User")
if ($path -split ";" -notcontains $binDir) {
    [Environment]::SetEnvironmentVariable("Path", "$path;$binDir", "User")
    Write-Host "  → Added $binDir to PATH (open a NEW terminal)" -ForegroundColor Yellow
}

# ---- Done ----
Write-Host ""
Write-Host "  ✓ BOYSER AI installed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "  Run:  boyser-ai" -ForegroundColor Cyan
Write-Host "  (Open a new terminal window first if PATH was just added)"
Write-Host ""
Write-Host "  First run will show the setup wizard to configure your backend/model."
Write-Host ""
