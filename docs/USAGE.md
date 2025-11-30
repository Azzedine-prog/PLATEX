# PLATEX Usage Guide

1. **Start the app**
   - Windows: double-click `setup_platform.bat` (first run installs prerequisites and launches the app).
   - macOS/Linux: run `./setup_platform.sh`.

2. **Create a project or open a `.tex` file**
   - Click **New Project Folder** to scaffold `main.tex`, `references.bib`, and an `images/` directory in one step, then start editing.
   - Or use the toolbar buttons for New/Open/Save on any existing `.tex` file, and keep multiple files open in tabs.
   - The **Project Files** panel on the left mirrors your working directory so you can double-click to open or switch files.
   - Use **New from Template** to start with article/report/beamer layouts.

3. **Compile to PDF & preview**
   - Live preview is on by default: keep typing and the PDF pane refreshes automatically after a short pause. Click **Live Preview** on the toolbar to pause/resume auto-compiles.
   - Click **Compile PDF** anytime for an immediate rebuild. The app searches for `latexmk`, `pdflatex`, or `xelatex` in your PATH and installs a toolchain automatically if missing.
   - The preview stays inside PLATEX; no external viewer is launched unless you click **Open PDF Externally** after a successful compile. When a compile fails, the preview switches to a readable log while the matching lines are tinted inside the editor for quick fixes.

4. **Faster authoring**
   - Right-click inside the editor to open the context menu: insert Overleaf-style snippets or **Add Figure from File** (copies your chosen image into the project `images/` folder and injects the LaTeX block).
- Use **Find…** from the Edit menu or toolbar to search within the current file.
- Use **Ask Document Assistant** from the Help menu to open the chat panel. It runs a tiny TensorFlow model locally (trained on first run). If TensorFlow is unavailable, the assistant still answers using built-in heuristics—no internet needed. The assistant reads your open project’s `.tex` files and quotes the most relevant snippet back in its reply so suggestions stay grounded in your actual document.

5. **Need a single executable?**
   - Run `python build.py` after installing dependencies to create `dist/platex` (or `dist/platex.exe` on Windows).

## Requirements
- Python 3.10+
- TensorFlow runtime (installed via `pip install -r requirements.txt`; if you skip it, the assistant will still reply with heuristics)
- LaTeX distribution with `latexmk`, `pdflatex`, or `xelatex` (setup scripts install TeX Live/MiKTeX automatically when possible)
- GUI environment (Qt requires a desktop session)

## Tips
- Keep your `.tex` files in a simple folder without spaces to avoid path issues on some TeX engines.
- Use the snippet dropdown on the toolbar or the editor right-click menu (figure, table, bibliography, section, equation, list, TOC, theorem, code) for quick Overleaf-style inserts.
- If compilation hangs, rerun the setup script so it can refresh/update the LaTeX distribution automatically.
