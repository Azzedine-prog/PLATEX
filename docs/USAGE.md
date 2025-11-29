# PLATEX Usage Guide

1. **Start the app**
   - Windows: double-click `setup_platform.bat` (first run installs prerequisites and launches the app).
   - macOS/Linux: run `./setup_platform.sh`.

2. **Create a project or open a `.tex` file**
   - Click **New Project Folder** to scaffold `main.tex`, `references.bib`, and an `images/` directory in one step, then start editing.
   - Or use the toolbar buttons for New/Open/Save on any existing `.tex` file.
   - Use **New from Template** to start with article/report/beamer layouts.

3. **Compile to PDF & preview**
   - Live preview is on by default: keep typing and the PDF pane refreshes automatically after a short pause. Click **Live Preview** on the toolbar to pause/resume auto-compiles.
   - Click **Compile PDF** anytime for an immediate rebuild. The app searches for `latexmk`, `pdflatex`, or `xelatex` in your PATH and installs a toolchain automatically if missing.
   - The preview stays inside PLATEX; no external viewer is launched unless you click **Open PDF Externally** after a successful compile.

4. **Need a single executable?**
   - Run `python build.py` after installing dependencies to create `dist/platex` (or `dist/platex.exe` on Windows).

## Requirements
- Python 3.10+
- LaTeX distribution with `latexmk`, `pdflatex`, or `xelatex` (setup scripts install TeX Live/MiKTeX automatically when possible)
- GUI environment (Qt requires a desktop session)

## Tips
- Keep your `.tex` files in a simple folder without spaces to avoid path issues on some TeX engines.
- Use the snippet buttons (figure, table, bibliography, section, equation, list, TOC, theorem, code) for quick Overleaf-style inserts.
- If compilation hangs, rerun the setup script so it can refresh/update the LaTeX distribution automatically.
