from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def clean_generated_files() -> None:
    for directory_name in (
        "__pycache__",
        ".pytest_cache",
    ):
        for path in PROJECT_ROOT.rglob(
            directory_name
        ):
            if path.is_dir():
                shutil.rmtree(
                    path,
                    ignore_errors=True,
                )

    for pattern in (
        "*.pyc",
        "*.pyo",
    ):
        for path in PROJECT_ROOT.rglob(
            pattern
        ):
            try:
                path.unlink()
            except OSError:
                pass


def run(
    *arguments: str,
) -> None:
    completed = subprocess.run(
        arguments,
        cwd=PROJECT_ROOT,
        check=False,
    )

    if completed.returncode:
        raise SystemExit(
            completed.returncode
        )


def main() -> None:
    clean_generated_files()
    run(
        sys.executable,
        "-m",
        "compileall",
        "-q",
        "src",
    )
    run(
        sys.executable,
        "-m",
        "pytest",
        "-q",
    )
    clean_generated_files()
    print(
        "Release-Prüfung erfolgreich. "
        "Generierte Python-Caches wurden entfernt."
    )


if __name__ == "__main__":
    main()
