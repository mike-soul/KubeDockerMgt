#Requires -Version 5.1
<#
.SYNOPSIS
    KubeDock installer — no admin required.
.DESCRIPTION
    1. Ensures Python 3.12 is present (installs per-user via winget if not)
    2. Downloads KubeDock from GitHub (or copies from a local path)
    3. Creates a venv in %LOCALAPPDATA%\KubeDock\
    4. Installs dependencies
    5. Drops a kubedock.bat launcher and adds it to the user PATH
.EXAMPLE
    # From GitHub (once you have a repo):
    irm https://raw.githubusercontent.com/YOU/kubedock/main/install.ps1 | iex

    # From a local directory (development / internal share):
    .\install.ps1
    .\install.ps1 -SourcePath "\\fileserver\tools\kubedock"
#>
param(
    # Local source directory to copy app files from.
    # When running via irm|iex this is ignored and files are pulled from GitHub.
    [string]$SourcePath = $PSScriptRoot,

    # Override the GitHub zip URL (tag/branch).
    [string]$GitHubZipUrl = "https://github.com/mike-soul/KubeDockerMgt/archive/refs/heads/main.zip"   # e.g. "https://github.com/YOU/kubedock/archive/refs/heads/main.zip"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
function Write-Step  { param([string]$msg) Write-Host "`n>>> $msg" -ForegroundColor Cyan }
function Write-OK    { param([string]$msg) Write-Host "    [OK] $msg" -ForegroundColor Green }
function Write-Warn  { param([string]$msg) Write-Host "    [!!] $msg" -ForegroundColor Yellow }
function Write-Fail  { param([string]$msg) Write-Host "`n[FAIL] $msg" -ForegroundColor Red; exit 1 }

function Add-ToUserPath {
    param([string]$Dir)
    $current = [Environment]::GetEnvironmentVariable("PATH", "User")
    if ($null -eq $current) { $current = "" }
    if ($current -split ";" -notcontains $Dir) {
        [Environment]::SetEnvironmentVariable("PATH", "$current;$Dir", "User")
        $env:PATH = "$env:PATH;$Dir"
        Write-OK "Added to user PATH: $Dir"
    } else {
        Write-OK "Already in user PATH: $Dir"
    }
}

function Refresh-PathFromRegistry {
    $machine = [Environment]::GetEnvironmentVariable("PATH", "Machine")
    $user    = [Environment]::GetEnvironmentVariable("PATH", "User")
    if ($null -eq $machine) { $machine = "" }
    if ($null -eq $user)    { $user    = "" }
    $env:PATH = "$machine;$user"
}

# ---------------------------------------------------------------------------
# Detect if running via irm | iex (PSScriptRoot will be empty)
# ---------------------------------------------------------------------------
$runningFromUrl = [string]::IsNullOrEmpty($PSScriptRoot)

# ---------------------------------------------------------------------------
# Step 1 — Ensure Python 3.12 is available (no admin needed)
# ---------------------------------------------------------------------------
Write-Step "Checking for Python..."

$pythonCmd = $null
foreach ($candidate in @("python", "python3", "py")) {
    try {
        $ver = & $candidate --version 2>&1
        if ($ver -match "Python 3\.") {
            $pythonCmd = $candidate
            Write-OK "Found: $ver  ($candidate)"
            break
        }
    } catch { }
}

if (-not $pythonCmd) {
    Write-Step "Python not found — installing via winget (user scope, no admin)..."

    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Fail "winget not found. Install 'App Installer' from the Microsoft Store or install Python manually from https://python.org and re-run."
    }

    winget install --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "winget install failed (exit $LASTEXITCODE). Try installing Python manually from https://python.org (choose 'Install for current user')."
    }

    Refresh-PathFromRegistry

    foreach ($candidate in @("python", "python3", "py")) {
        try {
            $ver = & $candidate --version 2>&1
            if ($ver -match "Python 3\.") { $pythonCmd = $candidate; break }
        } catch { }
    }

    if (-not $pythonCmd) {
        # winget may not have updated the current session PATH yet — find it manually
        $pyBase = Join-Path $env:LOCALAPPDATA "Programs\Python"
        $found  = Get-ChildItem $pyBase -Filter "python.exe" -Recurse -ErrorAction SilentlyContinue |
                  Sort-Object FullName -Descending | Select-Object -First 1
        if ($found) {
            $pythonCmd = $found.FullName
            Add-ToUserPath (Split-Path $found.FullName)
            Write-OK "Using: $pythonCmd"
        } else {
            Write-Fail "Python installed but could not locate python.exe. Please open a new terminal and re-run."
        }
    } else {
        Write-OK "Python installed successfully."
    }
}

# ---------------------------------------------------------------------------
# Step 2 — Resolve app source files
# ---------------------------------------------------------------------------
Write-Step "Resolving KubeDock source files..."

$installDir = Join-Path $env:LOCALAPPDATA "KubeDock"
$appStagingDir = Join-Path $env:TEMP "kubedock_staging"

if ($runningFromUrl -or $GitHubZipUrl) {
    # --- Download from GitHub ---
    if (-not $GitHubZipUrl) {
        Write-Fail "No GitHubZipUrl provided and script was run via irm|iex. Please set `$GitHubZipUrl or run the script with -GitHubZipUrl."
    }

    Write-OK "Downloading from: $GitHubZipUrl"
    $zipPath = Join-Path $env:TEMP "kubedock.zip"
    Invoke-WebRequest -Uri $GitHubZipUrl -OutFile $zipPath -UseBasicParsing

    if (Test-Path $appStagingDir) { Remove-Item $appStagingDir -Recurse -Force }
    Expand-Archive -Path $zipPath -DestinationPath $appStagingDir -Force
    Remove-Item $zipPath

    # GitHub zips extract into a subdirectory (repo-branch/)
    $inner = Get-ChildItem $appStagingDir -Directory | Select-Object -First 1
    if ($inner) { $sourceDir = $inner.FullName } else { $sourceDir = $appStagingDir }
} else {
    # --- Use local source (dev mode or UNC share) ---
    $sourceDir = $SourcePath
    if (-not (Test-Path (Join-Path $sourceDir "requirements.txt"))) {
        Write-Fail "Cannot find requirements.txt in '$sourceDir'. Run this script from the KubeDock project folder."
    }
    Write-OK "Source: $sourceDir"
}

# ---------------------------------------------------------------------------
# Step 3 — Copy files to install directory
# ---------------------------------------------------------------------------
Write-Step "Installing to $installDir ..."

if (-not (Test-Path $installDir)) { New-Item -ItemType Directory -Path $installDir | Out-Null }

# Copy app files (skip the venv folder if re-running)
$excludes = @("venv", ".git", "__pycache__", "*.pyc")
Get-ChildItem $sourceDir | Where-Object {
    $name = $_.Name
    -not ($excludes | Where-Object { $name -like $_ })
} | ForEach-Object {
    Copy-Item $_.FullName (Join-Path $installDir $_.Name) -Recurse -Force
}
Write-OK "Files copied."

# ---------------------------------------------------------------------------
# Step 4 — Create / update venv
# ---------------------------------------------------------------------------
Write-Step "Setting up Python virtual environment..."

$venvDir = Join-Path $installDir "venv"
if (-not (Test-Path $venvDir)) {
    & $pythonCmd -m venv $venvDir
    Write-OK "venv created."
} else {
    Write-OK "venv already exists — updating."
}

$pip = Join-Path $venvDir "Scripts\pip.exe"
if (-not (Test-Path $pip)) { Write-Fail "pip not found in venv. Try deleting '$venvDir' and re-running." }

Write-Step "Installing Python dependencies (this may take a minute)..."
& $pip install --upgrade pip --quiet
& $pip install -r (Join-Path $installDir "requirements.txt") --quiet
if ($LASTEXITCODE -ne 0) { Write-Fail "pip install failed." }
Write-OK "Dependencies installed."

# ---------------------------------------------------------------------------
# Step 5 — Create launcher batch file
# ---------------------------------------------------------------------------
Write-Step "Creating launcher..."

$launcherDir  = Join-Path $env:LOCALAPPDATA "KubeDock\bin"
$launcherPath = Join-Path $launcherDir "kubedock.bat"

if (-not (Test-Path $launcherDir)) { New-Item -ItemType Directory -Path $launcherDir | Out-Null }

$venvPython = Join-Path $venvDir "Scripts\python.exe"
$mainScript  = Join-Path $installDir "main.py"

@"
@echo off
"$venvPython" "$mainScript" %*
"@ | Set-Content $launcherPath -Encoding ASCII

Write-OK "Launcher: $launcherPath"

# ---------------------------------------------------------------------------
# Step 6 — Add launcher directory to user PATH
# ---------------------------------------------------------------------------
Write-Step "Updating user PATH..."
Add-ToUserPath $launcherDir

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  KubeDock installed successfully!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Run it:   kubedock" -ForegroundColor White
Write-Host ""
Write-Host "  Note: If 'kubedock' is not found, open a new terminal window" -ForegroundColor Yellow
Write-Host "        (PATH changes require a new session to take effect)." -ForegroundColor Yellow
Write-Host ""
