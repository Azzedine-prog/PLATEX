# PLATEX – Lightweight Desktop LaTeX Editor (Python + Qt)

PLATEX is now a simple, cross-platform desktop LaTeX editor built with Python and Qt. It saves `.tex` files locally and can call your installed LaTeX distribution (TeX Live or MiKTeX) to produce PDFs. Everything ships as a single runnable application that you can launch directly or package via PyInstaller.

## What you get
- A friendly Qt editor with open/save, toolbar shortcuts, and a one-click **Compile PDF** button.
- Automatic detection of `pdflatex` or `xelatex` (whichever is available in your PATH).
- Double-click installers for Windows plus single-command setup for macOS/Linux.
- One-file binary builds via PyInstaller (`platex.exe` on Windows, `platex` on macOS/Linux).

## Quick start for non-technical users
### Windows (double-click)
1. Download `setup_platform.bat` from this repository.
2. Place it in a folder and double-click it. The batch file launches PowerShell to:
   - Ensure Python 3.10+ is installed (installs via `winget` when available).
   - Install required Python libraries.
   - Launch PLATEX immediately.
3. After the first run, you can start PLATEX by double-clicking the generated shortcut or running `platex.exe` from the `dist` folder.

### macOS / Linux (single command)
```bash
curl -fsSL https://raw.githubusercontent.com/example/PLATEX/main/setup_platform.sh | bash
```
- The script verifies Python 3.10+, installs dependencies with `pip`, and launches the Qt app.

## Building a single-file executable (advanced users)
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python build.py
```
- Output is written to `dist/platex.exe` (Windows) or `dist/platex` (macOS/Linux).

## Running from source
```bash
pip install -r requirements.txt
python app/main.py
```

## Troubleshooting
- **"No LaTeX compiler found"**: Install TeX Live (macOS/Linux) or MiKTeX (Windows) so `pdflatex` or `xelatex` is available in PATH.
- **PyInstaller antivirus false positives**: Rebuild locally with `python build.py` so the binary is signed with your own environment.
- **Missing GUI on Linux**: Ensure an X11/Wayland environment is available; install `qtwayland5` on some distributions if needed.

## Project structure
```
app/            # Qt application source
build.py        # PyInstaller one-file build helper
docs/           # Usage notes
requirements.txt
setup_platform.*  # Platform-specific launchers
```

## License
This project is provided as-is for demonstration purposes.
