#!/usr/bin/env bash
set -euo pipefail

REPO_URL=${REPO_URL:-"https://github.com/example/PLATEX.git"}
PROJECT_DIR=${PROJECT_DIR:-"PLATEX"}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

install_docker() {
  echo "Docker not found. Attempting installation..."
  if command_exists apt-get; then
    sudo apt-get update && sudo apt-get install -y docker.io
    sudo systemctl enable --now docker
  elif command_exists brew; then
    brew install --cask docker || brew install docker
    echo "Please start the Docker app if it is not already running."
  else
    echo "Please install Docker manually from https://docs.docker.com/get-docker/" && exit 1
  fi
}

install_node() {
  echo "Node.js not found. Attempting installation..."
  if command_exists apt-get; then
    sudo apt-get update && sudo apt-get install -y nodejs npm
  elif command_exists brew; then
    brew install node
  else
    echo "Please install Node.js manually from https://nodejs.org/en/download/" && exit 1
  fi
}

ensure_prerequisites() {
  command_exists docker || install_docker
  command_exists node || install_node
}

clone_repo() {
  if [ ! -d "$PROJECT_DIR/.git" ]; then
    echo "Cloning PLATEX repository from $REPO_URL ..."
    git clone "$REPO_URL" "$PROJECT_DIR"
  else
    echo "Repository already present at $PROJECT_DIR. Skipping clone."
  fi
}

start_stack() {
  pushd "$PROJECT_DIR" >/dev/null
  echo "Starting PLATEX stack via docker-compose..."
  docker compose up -d --build
  popd >/dev/null
}

print_banner() {
  cat <<'MSG'
========================================
PLATEX installation complete.
Backend: http://localhost:3000
Compilation service: http://localhost:7000
========================================
MSG
}

main() {
  ensure_prerequisites
  clone_repo
  start_stack
  print_banner
}

main "$@"
