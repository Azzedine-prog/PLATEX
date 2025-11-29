Param(
    [string]$RepoUrl = "https://github.com/example/PLATEX.git",
    [string]$ProjectDir = "PLATEX"
)

$ErrorActionPreference = "Stop"

function CommandExists($cmd) {
    $null -ne (Get-Command $cmd -ErrorAction SilentlyContinue)
}

function InstallWithWinget($id, $friendly) {
    if (-not (CommandExists "winget")) {
        Write-Host "winget not found. Please install $friendly manually." -ForegroundColor Yellow
        return $false
    }
    Write-Host "Installing $friendly via winget..." -ForegroundColor Cyan
    winget install --id $id -e --silent -h
    return $true
}

function EnsureDocker {
    if (CommandExists "docker") { return }
    if (-not (InstallWithWinget "Docker.DockerDesktop" "Docker Desktop")) {
        Write-Host "Docker not found. Install Docker Desktop from https://www.docker.com/products/docker-desktop and restart PowerShell." -ForegroundColor Yellow
        exit 1
    }
    Write-Host "Docker Desktop installed. Please ensure it is running before continuing." -ForegroundColor Yellow
}

function EnsureNode {
    if (CommandExists "node") { return }
    if (-not (InstallWithWinget "OpenJS.NodeJS.LTS" "Node.js LTS")) {
        Write-Host "Node.js not found. Install from https://nodejs.org/en/download and restart PowerShell." -ForegroundColor Yellow
        exit 1
    }
}

function EnsureGit {
    if (CommandExists "git") { return }
    if (-not (InstallWithWinget "Git.Git" "Git")) {
        Write-Host "Git not found. Install from https://git-scm.com/downloads and restart PowerShell." -ForegroundColor Yellow
        exit 1
    }
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
    Write-Host "If Docker Desktop was installed just now, please ensure it is running."
    Write-Host "========================================"
}

EnsureGit
EnsureDocker
EnsureNode
CloneRepo
StartStack
PrintBanner
