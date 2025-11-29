import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent
MAIN_FILE = PROJECT_ROOT / "app" / "main.py"
DIST_DIR = PROJECT_ROOT / "dist"


def build() -> int:
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--name",
        "platex",
        str(MAIN_FILE),
    ]
    print("Running:", " ".join(command))
    result = subprocess.run(command, cwd=PROJECT_ROOT)
    if result.returncode == 0:
        built = DIST_DIR / ("platex.exe" if sys.platform == "win32" else "platex")
        print(f"Build succeeded → {built}")
    else:
        print("Build failed")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(build())
