import os
from pathlib import Path
import subprocess
import sys

PROJECT_DIR = Path(__file__).resolve().parent
VENDOR_DIR = PROJECT_DIR / ".vendor"
BUNDLED_PYTHON = Path(
    r"C:\Users\hakot\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
)
BOOTSTRAP_FLAG = "QARYZCALC_BOOTSTRAPPED"


def _vendor_requires_python_312() -> bool:
    numpy_binary = VENDOR_DIR / "numpy" / "_core" / "_multiarray_umath.cp312-win_amd64.pyd"
    return numpy_binary.exists()


def _should_relaunch_with_bundled_python() -> bool:
    return (
        VENDOR_DIR.exists()
        and _vendor_requires_python_312()
        and sys.version_info[:2] != (3, 12)
        and BUNDLED_PYTHON.exists()
        and os.environ.get(BOOTSTRAP_FLAG) != "1"
        and Path(sys.executable).resolve() != BUNDLED_PYTHON.resolve()
    )


def _relaunch_with_bundled_python() -> None:
    env = os.environ.copy()
    env[BOOTSTRAP_FLAG] = "1"
    result = subprocess.run([str(BUNDLED_PYTHON), str(PROJECT_DIR / "main.py"), *sys.argv[1:]], env=env)
    raise SystemExit(result.returncode)


if _should_relaunch_with_bundled_python():
    _relaunch_with_bundled_python()

if VENDOR_DIR.exists():
    sys.path.insert(0, str(VENDOR_DIR))

from qaryzcalc.ui.app import run


if __name__ == "__main__":
    run()
