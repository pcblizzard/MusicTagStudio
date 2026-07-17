from __future__ import annotations

import subprocess
import sys


def run(
    *arguments: str,
) -> None:
    completed = subprocess.run(
        arguments,
        check=False,
    )

    if completed.returncode:
        raise SystemExit(
            completed.returncode
        )


def main() -> None:
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
    print(
        "Release-Prüfung erfolgreich."
    )


if __name__ == "__main__":
    main()
