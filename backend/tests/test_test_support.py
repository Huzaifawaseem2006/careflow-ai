"""Tooling regressions use synthetic data and real process boundaries."""

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

from scripts import test_support


def test_private_temp_probe_checks_access_and_cleans_up(tmp_path: Path) -> None:
    test_support.check_private_temp(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_private_temp_probe_fails_with_actionable_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def denied(*args: object, **kwargs: object) -> None:
        raise PermissionError("synthetic secret must not appear")

    monkeypatch.setattr(Path, "write_text", denied)
    with pytest.raises(RuntimeError, match="normal Windows PowerShell") as error:
        test_support.check_private_temp(tmp_path)
    assert "synthetic secret" not in str(error.value)


def test_timeout_terminates_descendant_before_it_can_write(tmp_path: Path) -> None:
    marker = tmp_path / "leaked.json"
    grandchild = (
        "import time,pathlib; time.sleep(3); "
        f"pathlib.Path({str(marker)!r}).write_text('leaked')"
    )
    child = (
        "import subprocess,sys,time; "
        f"subprocess.Popen([sys.executable,'-c',{grandchild!r}]); "
        "print('started',flush=True); time.sleep(30)"
    )
    started = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired) as error:
        test_support.run_process([sys.executable, "-c", child], timeout=1, cwd=tmp_path)
    assert time.monotonic() - started < 2.5
    assert "started" in error.value.output
    time.sleep(3)
    assert not marker.exists()


def test_process_result_preserves_output_and_failure(tmp_path: Path) -> None:
    result = test_support.run_process(
        [sys.executable, "-c", "import sys; print('synthetic'); sys.exit(7)"],
        timeout=10,
        cwd=tmp_path,
    )
    assert result.returncode == 7
    assert result.stdout.strip() == "synthetic"


def test_timings_record_only_labels_and_elapsed_values(tmp_path: Path) -> None:
    recorder = test_support.Timings()
    with recorder.measure("migrations"):
        pass
    output = tmp_path / "timings.json"
    recorder.save(output)
    data = json.loads(output.read_text())
    assert data["migrations"]["count"] == 1
    assert data["migrations"]["seconds"] >= 0
    with pytest.raises(ValueError):
        with recorder.measure("postgresql://synthetic:secret@host/db"):
            pass
