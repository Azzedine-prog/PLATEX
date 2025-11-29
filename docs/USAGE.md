# PLATEX Usage Guide

1. **Start the app**
   - Windows: double-click `setup_platform.bat` (first run installs prerequisites and launches the app).
   - macOS/Linux: run `./setup_platform.sh`.

2. **Create or open a `.tex` file**
   - Use the toolbar buttons for New/Open/Save.

3. **Compile to PDF**
   - Click **Compile PDF**.
   - The app searches for `pdflatex` or `xelatex` in your PATH.
   - Output PDF is placed next to your `.tex` file and displayed in the live preview pane; it also opens with your system viewer if the preview cannot load.

4. **Need a single executable?**
   - Run `python build.py` after installing dependencies to create `dist/platex` (or `dist/platex.exe` on Windows).

## Requirements
- Python 3.10+
- LaTeX distribution with `pdflatex` or `xelatex` (TeX Live or MiKTeX)
- GUI environment (Qt requires a desktop session)

## Tips
- Keep your `.tex` files in a simple folder without spaces to avoid path issues on some TeX engines.
- If compilation hangs, check for missing packages in your LaTeX distribution.
