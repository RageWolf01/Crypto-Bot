"""Launcher for the scheduled digest.

Windows Task Scheduler does not set a working directory, so this file puts the
project root on the import path before starting the CLI. Point the scheduled task
at this script rather than at ``-m crypto_advisor``.
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from crypto_advisor.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(["run", "--quiet"]))
