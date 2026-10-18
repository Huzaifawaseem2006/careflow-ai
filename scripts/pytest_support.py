"""Fixed pytest preflight and numeric-only timing evidence."""

import json
from pathlib import Path

import pytest

from scripts.test_support import Timings, check_private_temp

TIMINGS = Timings()
OUTPUT: Path | None = None
CONFIG: pytest.Config | None = None


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--careflow-timings", type=Path, default=None)


def pytest_sessionstart(session: pytest.Session) -> None:
    global OUTPUT, CONFIG
    OUTPUT = session.config.getoption("--careflow-timings")
    CONFIG = session.config
    TIMINGS.values.clear()
    try:
        check_private_temp(session.config.rootpath / "test-results")
    except RuntimeError as error:
        raise pytest.UsageError(str(error)) from None


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_logstart(nodeid: str) -> None:
    if OUTPUT is not None and CONFIG is not None:
        reporter = CONFIG.pluginmanager.getplugin("terminalreporter")
        if reporter is not None:
            # Parameter representations can contain configuration; omit them.
            reporter.write_line("Starting " + nodeid.split("[", 1)[0])


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if report.when in {"setup", "call", "teardown"}:
        TIMINGS.add(report.when, report.duration)
        if report.when == "teardown" and OUTPUT is not None:
            TIMINGS.save(OUTPUT)


def pytest_sessionfinish(session: pytest.Session) -> None:
    output = session.config.getoption("--careflow-timings")
    if output is not None:
        TIMINGS.save(output)
        reporter = session.config.pluginmanager.getplugin("terminalreporter")
        if reporter is not None:
            reporter.write_line("Numeric stage timings: " + json.dumps(TIMINGS.values))
