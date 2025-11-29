# PLATEX Usage Guide

1. **Start the app**
   - Windows: double-click `setup_platform.bat` (first run installs prerequisites and launches the app).
   - macOS/Linux: run `./setup_platform.sh`.

2. **Create or open a `.tex` file**
   - Use the toolbar buttons for New/Open/Save.
   - Use **New from Template** to start with article/report/beamer layouts.

3. **Compile to PDF**
   - Click **Compile PDF**.
   - The app searches for `latexmk`, `pdflatex`, or `xelatex` in your PATH and installs a toolchain automatically if missing.
   - Output PDF is placed next to your `.tex` file and displayed in the live preview pane; it also opens with your system viewer if the preview cannot load.

4. **Need a single executable?**
   - Run `python build.py` after installing dependencies to create `dist/platex` (or `dist/platex.exe` on Windows).

## Requirements
- Python 3.10+
- LaTeX distribution with `latexmk`, `pdflatex`, or `xelatex` (setup scripts install TeX Live/MiKTeX automatically when possible)
- GUI environment (Qt requires a desktop session)

## Tips
- Keep your `.tex` files in a simple folder without spaces to avoid path issues on some TeX engines.
- If compilation hangs, rerun the setup script so it can refresh/update the LaTeX distribution automatically.
