#Requires -Version 5.1
<#
.SYNOPSIS
    Downloads all Python dependency wheels into the wheels/ folder.
.DESCRIPTION
    Run this once (or after changing requirements.txt) before pushing to GitHub.
    The wheels/ folder is committed to the repo so installs never hit PyPI.
.EXAMPLE
    .\vendor.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$wheelsDir = Join-Path $PSScriptRoot "wheels"

# Ensure py is available
if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    Write-Host "[FAIL] Python launcher (py) not found. Install Python from https://python.org first." -ForegroundColor Red
    exit 1
}

Write-Host "Downloading wheels into: $wheelsDir" -ForegroundColor Cyan

if (Test-Path $wheelsDir) {
    Remove-Item $wheelsDir -Recurse -Force
}
New-Item -ItemType Directory -Path $wheelsDir | Out-Null

$reqFile = Join-Path $PSScriptRoot "requirements.txt"
py -3.12 -m pip download -r $reqFile -d $wheelsDir

if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAIL] pip download failed." -ForegroundColor Red
    exit 1
}

$count = (Get-ChildItem $wheelsDir -Filter "*.whl").Count
Write-Host ""
Write-Host "Done - $count wheel files saved to wheels/" -ForegroundColor Green
Write-Host "Commit the wheels/ folder and push." -ForegroundColor Yellow
