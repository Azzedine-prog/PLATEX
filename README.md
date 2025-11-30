# PLATEX – Lightweight Desktop LaTeX Editor (Python + Qt)

PLATEX is now a simple, cross-platform desktop LaTeX editor built with Python and Qt. It saves `.tex` files locally and can call your installed LaTeX distribution (TeX Live or MiKTeX) to produce PDFs. Everything ships as a single runnable application that you can launch directly or package via PyInstaller.

## What you get
- A LinkedIn-inspired, modern Qt editor with tabs for open files, a left-hand **Project Files** browser, menu bar shortcuts, **project folders**, a one-click **Compile PDF** button, **syntax highlighting**, and a built-in split-view PDF preview (no external viewer pops up unless you ask). When compilation fails, the preview pane flips to a readable log with inline error highlights in the editor. The refreshed palette, typography, and tab/tree styling keep the UI polished and consistent.
- Automatic detection of `latexmk`, `pdflatex`, or `xelatex` (whichever is available) with silent one-time installation when missing.
- Double-click installers for Windows plus single-command setup for macOS/Linux.
- One-file binary builds via PyInstaller (`platex.exe` on Windows, `platex` on macOS/Linux).
- Starter templates (article/report/beamer) plus richer Overleaf-style snippets (figures, tables, bibliography, sections, equations, lists, table of contents, theorems, code listings) available from the toolbar dropdown, context menu, and menu bar, and "New Project" scaffolding with `main.tex`, `references.bib`, and an `images/` folder. A dedicated **Add Figure from File** workflow copies images into your project and injects the LaTeX block automatically, and a **Find** command makes in-file search quick. A TensorFlow-powered **Document Assistant** (downloads or trains a tiny model locally) chats about your document offline—structure tips, figure guidance, compile fixes—without sending data anywhere.

## Quick start for non-technical users
### Windows (double-click)
1. Download `setup_platform.bat` from this repository.
2. Place it in a folder and double-click it. The batch file launches PowerShell to:
   - Ensure Python 3.10+ is installed (installs via `winget` when available).
   - Install required Python libraries.
   - Install MiKTeX silently (via `winget`) if LaTeX is missing, preloading recommended packages to avoid prompts.
   - Launch PLATEX immediately.
3. After the first run, you can start PLATEX by double-clicking the generated shortcut or running `platex.exe` from the `dist` folder.

### macOS / Linux (single command)
```bash
curl -fsSL https://raw.githubusercontent.com/example/PLATEX/main/setup_platform.sh | bash
```
- The script verifies Python 3.10+, installs dependencies with `pip`, and launches the Qt app.
- If no LaTeX toolchain is detected, it installs TeX Live (via `apt-get`) or BasicTeX (via Homebrew) and adds `latexmk`.

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
- On first launch the **Document Assistant** will try to download a tiny TensorFlow intent model; if it cannot, it trains a small local one automatically so responses stay offline.
- Use **New Project Folder** to scaffold a ready-to-edit workspace with `main.tex`, `references.bib`, and `images/`.
- Live preview is on by default: keep typing and the PDF pane quietly refreshes after a short pause. Toggle **Live Preview** on the toolbar to pause/resume auto-compiles. Use **Open PDF Externally** when you explicitly want the generated file in your system viewer. Tabs keep multiple `.tex` files open at once while the left **Project Files** tree mirrors your folder for quick double-click opens. If a build fails, the preview pane shows the compiler log instead of an empty PDF, and matching lines are tinted inline in the editor.
- Use **New from Template** for an article/report/beamer starter, and the toolbar snippets (figure/table/bibliography/section/equation/list/TOC/theorem/code) to insert common blocks quickly. The context menu also includes **Add Figure from File** to copy an image into your project `images/` folder and drop in the LaTeX block, plus a **Find…** command for inline searching.

## Troubleshooting
- **"No LaTeX compiler found"**: Re-run the platform script; it now installs TeX Live/MiKTeX automatically when possible.
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
