"""Local test infrastructure; never log command environments or SQL values."""

import json
import os
import signal
import subprocess
import sys
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from time import perf_counter
from uuid import uuid4

STAGES = frozenset(
    {
        "database_create",
        "database_drop",
        "migrations",
        "fixtures",
        "catalog",
        "accounts",
        "schedule",
        "subprocess",
        "setup",
        "call",
        "teardown",
    }
)


class Timings:
    def __init__(self) -> None:
        self.values: dict[str, dict[str, float | int]] = {}

    @contextmanager
    def measure(self, stage: str) -> Iterator[None]:
        if stage not in STAGES:
            raise ValueError("Unknown timing stage")
        started = perf_counter()
        try:
            yield
        finally:
            self.add(stage, perf_counter() - started)

    def add(self, stage: str, seconds: float) -> None:
        if stage not in STAGES:
            raise ValueError("Unknown timing stage")
        entry = self.values.setdefault(stage, {"count": 0, "seconds": 0.0})
        entry["count"] += 1
        entry["seconds"] += seconds

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.values, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)


def check_private_temp(parent: Path) -> None:
    """Exercise the same private mode pytest needs; do not relax its ACLs."""
    directory = parent / ("private-preflight-" + uuid4().hex)
    probe = directory / "probe"
    try:
        parent.mkdir(parents=True, exist_ok=True)
        directory.mkdir(mode=0o700)
        probe.write_text("synthetic test probe", encoding="utf-8")
        if probe not in list(directory.iterdir()):
            raise OSError("Cannot list private temporary directory")
        probe.unlink()
        directory.rmdir()
    except OSError:
        # Best effort on our own two paths only. An incompatible restricted token
        # may be unable to remove the directory it just created.
        try:
            probe.unlink(missing_ok=True)
            directory.rmdir()
        except OSError:
            pass
        raise RuntimeError(
            "Private pytest temporary-directory access failed. Run this same "
            "command from normal Windows PowerShell (normal-host execution). "
            "Do not relax temporary-directory or credential permissions."
        ) from None


def run_process(
    command: Sequence[str], *, timeout: float, cwd: Path
) -> subprocess.CompletedProcess[str]:
    arguments = list(command)
    if sys.platform == "win32":
        arguments = [
            sys.executable,
            str(Path(__file__).with_name("process_worker.py")),
            *arguments,
        ]
    with subprocess.Popen(
        arguments,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=sys.platform != "win32",
    ) as process:
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            if sys.platform == "win32":
                process.kill()  # Closing the supervisor's job kills descendants.
            else:
                os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate(timeout=5)
            raise subprocess.TimeoutExpired(command, timeout, stdout, stderr) from None
        finally:
            if sys.platform != "win32":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        return subprocess.CompletedProcess(
            list(command), process.returncode, stdout, stderr
        )
