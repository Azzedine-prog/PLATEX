Param(
    [string]$RepoUrl = "https://github.com/example/PLATEX.git",
    [string]$ProjectDir = "PLATEX"
)

$ErrorActionPreference = "Stop"

function CommandExists($cmd) {
    $null -ne (Get-Command $cmd -ErrorAction SilentlyContinue)
}

function EnsureDocker {
    if (CommandExists "docker") { return }
    Write-Host "Docker not found. Install Docker Desktop from https://www.docker.com/products/docker-desktop and restart PowerShell." -ForegroundColor Yellow
    exit 1
}

function EnsureNode {
    if (CommandExists "node") { return }
    Write-Host "Node.js not found. Install from https://nodejs.org/en/download and restart PowerShell." -ForegroundColor Yellow
    exit 1
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

function StartStack {
    Push-Location $ProjectDir
    Write-Host "Starting PLATEX stack via docker compose..." -ForegroundColor Cyan
    docker compose up -d --build
    Pop-Location
}

function PrintBanner {
    Write-Host "========================================"
    Write-Host "PLATEX installation complete."
    Write-Host "Backend: http://localhost:3000"
    Write-Host "Compilation service: http://localhost:7000"
    Write-Host "========================================"
}

EnsureDocker
EnsureNode
CloneRepo
StartStack
PrintBanner
