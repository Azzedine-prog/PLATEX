#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/example/PLATEX.git"
PROJECT_DIR="PLATEX"

need_cmd() {
  command -v "$1" >/dev/null 2>&1
}

ensure_python() {
  if need_cmd python3; then
    PYTHON=python3
    return
  fi
  echo "Python 3.10+ is required." >&2
  if [[ "$(uname -s)" == "Darwin" ]] && need_cmd brew; then
    echo "Installing Python via Homebrew..."
    brew install python@3 || true
  elif need_cmd apt-get; then
    echo "Installing Python via apt..."
    sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip
  else
    echo "Please install Python manually from https://www.python.org/downloads/" >&2
    exit 1
  fi
  PYTHON=python3
}

ensure_git() {
  if need_cmd git; then return; fi
  if need_cmd apt-get; then
    sudo apt-get update && sudo apt-get install -y git
  elif [[ "$(uname -s)" == "Darwin" ]] && need_cmd brew; then
    brew install git
  else
    echo "Git is required. Install from https://git-scm.com/downloads" >&2
    exit 1
  fi
}

clone_repo() {
  if [ ! -d "$PROJECT_DIR/.git" ]; then
    git clone "$REPO_URL" "$PROJECT_DIR"
  else
    echo "Repository already present at $PROJECT_DIR"
  fi
}

install_deps() {
  cd "$PROJECT_DIR"
  $PYTHON -m pip install --upgrade pip
  $PYTHON -m pip install -r requirements.txt
  cd - >/dev/null
}

install_latex() {
  if command -v pdflatex >/dev/null 2>&1 || command -v xelatex >/dev/null 2>&1 || command -v latexmk >/dev/null 2>&1; then
    return
  fi

  echo "Installing LaTeX toolchain (one-time setup)…"
  if [[ "$(uname -s)" == "Darwin" ]] && need_cmd brew; then
    brew install --cask basictex || true
    sudo /Library/TeX/texbin/tlmgr install latexmk || true
  elif need_cmd apt-get; then
    sudo apt-get update
    sudo apt-get install -y texlive-full latexmk
  else
    echo "No supported package manager found. Please install TeX Live or MiKTeX manually." >&2
  fi
}

build_if_possible() {
  cd "$PROJECT_DIR"
  echo "Building one-file executable with PyInstaller (optional)..."
  if ! $PYTHON build.py; then
    echo "Build failed; will run from source." >&2
  fi
  cd - >/dev/null
}

launch_app() {
  cd "$PROJECT_DIR"
  if [ -f dist/platex ]; then
    echo "Launching packaged app..."
    ./dist/platex &
  else
    echo "Launching from source..."
    $PYTHON app/main.py &
  fi
  cd - >/dev/null
}

banner() {
  cat <<'EOF'
