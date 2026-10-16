"""Run foundation checks from the checkout root using the active Python."""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report", type=Path, default=Path("test-results/foundation.json")
    )
    options = parser.parse_args()
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
        ],
    }
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], text=True))
    checks: list[dict[str, object]] = []
    for name, arguments in commands.items():
        result = subprocess.run([sys.executable, "-m", *arguments], check=False)
        checks.append(
            {
                "name": name,
                "command": [sys.executable, "-m", *arguments],
                "exit_code": result.returncode,
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
