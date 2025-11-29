Param(
    [string]$RepoUrl = "https://github.com/example/PLATEX.git",
    [string]$ProjectDir = "PLATEX"
)

$ErrorActionPreference = "Stop"

function CommandExists($cmd) {
    $null -ne (Get-Command $cmd -ErrorAction SilentlyContinue)
}

function EnsurePython {
    if (CommandExists "python") { return }
    if (-not (CommandExists "winget")) {
        Write-Host "Python 3.10+ is required. Install from https://www.python.org/downloads/ and re-run this script." -ForegroundColor Yellow
        exit 1
    }
    Write-Host "Installing Python via winget..." -ForegroundColor Cyan
    winget install --id Python.Python.3.12 -e --silent -h
}

function EnsureGit {
    if (CommandExists "git") { return }
    if (-not (CommandExists "winget")) {
        Write-Host "Git is required. Install from https://git-scm.com/downloads and re-run this script." -ForegroundColor Yellow
        exit 1
    }
    Write-Host "Installing Git via winget..." -ForegroundColor Cyan
    winget install --id Git.Git -e --silent -h
}

function CloneRepo {
    if (-Not (Test-Path "$ProjectDir/.git")) {
        Write-Host "Cloning PLATEX repository from $RepoUrl ..." -ForegroundColor Cyan
        git clone $RepoUrl $ProjectDir
    }
    else {
        Write-Host "Repository already present at $ProjectDir. Skipping clone." -ForegroundColor Green
    }
}

function InstallDeps {
    Push-Location $ProjectDir
    Write-Host "Installing Python dependencies..." -ForegroundColor Cyan
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    Pop-Location
}

function BuildIfPossible {
    Push-Location $ProjectDir
    try {
        Write-Host "Building one-file executable with PyInstaller..." -ForegroundColor Cyan
        python build.py
    }
    catch {
        Write-Host "PyInstaller build failed; running from source instead." -ForegroundColor Yellow
    }
    Pop-Location
}

function LaunchApp {
    Push-Location $ProjectDir
    $exe = Join-Path "dist" "platex.exe"
    if (Test-Path $exe) {
        Write-Host "Launching packaged app..." -ForegroundColor Green
        & $exe
    }
    else {
        Write-Host "Launching from source..." -ForegroundColor Green
        python app/main.py
    }
    Pop-Location
}

function PrintBanner {
    Write-Host "========================================"
    Write-Host "PLATEX is ready."
    Write-Host "Double-click setup_platform.bat next time to start quickly."
    Write-Host "========================================"
}

EnsureGit
EnsurePython
CloneRepo
InstallDeps
BuildIfPossible
PrintBanner
LaunchApp
