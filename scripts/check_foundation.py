"""Run foundation checks from the checkout root using the active Python."""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from time import perf_counter

# Support execution both as a script and as a module.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.test_support import check_private_temp  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report", type=Path, default=Path("test-results/foundation.json")
    )
    options = parser.parse_args()
    try:
        check_private_temp(options.report.parent)
    except RuntimeError as error:
        print(str(error), flush=True)
        return 1
    targets = ["backend", "scripts", "ci_tests", "evals"]
    commands = {
        "format": ["ruff", "format", "--check", *targets],
        "lint": ["ruff", "check", *targets],
        "types": ["mypy", *targets],
        "unit": [
            "pytest",
            "backend/tests",
            "evals/tests",
            "-q",
            "--junitxml",
            str(options.report.with_suffix(".xml")),
            "--basetemp",
            str(options.report.parent / (options.report.stem + "-unit-temp")),
            "-p",
            "no:cacheprovider",
            "--durations=15",
        ],
    }
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], text=True))
    checks: list[dict[str, object]] = []
    for name, arguments in commands.items():
        print(f"Starting {name} check", flush=True)
        started = perf_counter()
        result = subprocess.run([sys.executable, "-m", *arguments], check=False)
        seconds = perf_counter() - started
        print(
            f"Finished {name} check: exit {result.returncode}, {seconds:.2f}s",
            flush=True,
        )
        checks.append(
            {
                "name": name,
                "command": [sys.executable, "-m", *arguments],
                "exit_code": result.returncode,
                "seconds": seconds,
            }
        )
    failed = any(check["exit_code"] != 0 for check in checks)
    report = {
        "revision": revision,
        "dirty": dirty,
        "result": "failed" if failed else "passed",
        "checks": checks,
    }
    output = options.report
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
