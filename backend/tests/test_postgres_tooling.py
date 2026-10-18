"""Credential tooling checks use synthetic secrets; no PostgreSQL is required."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

import pytest

from scripts import postgres_test_runner as runner

URL = "postgresql+psycopg://postgres:synthetic%40password@127.0.0.1:5432/postgres"


@pytest.mark.parametrize(
    "url",
    [
        "",
        "not a URL",
        URL.replace("/postgres", "/careflow_ai"),
        URL.replace("127.0.0.1", "example.com"),
        URL + "?host=example.com",
        URL.replace(":5432", ":5433"),
        URL.replace("postgres:", "other:"),
        URL.replace("postgresql+psycopg", "postgresql"),
        URL.replace("synthetic%40password", ""),
        URL.replace("synthetic%40password", "line%0Abreak"),
    ],
)
def test_unsafe_targets_rejected(url: str) -> None:
    with pytest.raises(ValueError):
        runner.checked_url(url)


def test_redaction_and_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    url, password = runner.checked_url(URL)
    text = f"{url} {password} {quote(password, safe='')} postgresql://postgres:anything@localhost/postgres"
    result = runner.redact(text, url, password)
    assert password not in result and "synthetic" not in result
    assert "postgresql" not in result
    for name in (
        "DATABASE_URL",
        "PGPASSWORD",
        "PGSERVICE",
        "PYTEST_ADDOPTS",
        "PYTEST_PLUGINS",
        "ANTHROPIC_API_KEY",
    ):
        monkeypatch.setenv(name, "synthetic-parent-sentinel")
    monkeypatch.setenv("TEST_DATABASE_URL", "synthetic-parent-sentinel")
    environment = runner.child_environment(url)
    assert environment["TEST_DATABASE_URL"] == url
    assert environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
    assert "synthetic-parent-sentinel" not in environment.values()
    assert os.environ["TEST_DATABASE_URL"] == "synthetic-parent-sentinel"


def test_failures_do_not_print_connection_errors(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("TEST_DATABASE_URL", URL)
    monkeypatch.setattr(sys, "argv", ["runner", "validate"])

    def fail(url: str) -> set[str]:
        raise RuntimeError(url + " synthetic@password")

    monkeypatch.setattr(runner, "disposable_names", fail)
    assert runner.main() == 1
    output = capsys.readouterr()
    assert "synthetic" not in output.out + output.err


def test_missing_credentials_fail_closed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    assert runner.main() == 1
    assert "No secret details" in capsys.readouterr().out


@pytest.mark.parametrize(
    "path",
    [
        "backend/tests",
        "../careflow_ai",
        "-s",
        "backend/integration_tests/../tests",
        "backend/integration_tests/test_a.py --showlocals",
    ],
)
def test_test_selection_cannot_inject_arguments(path: str) -> None:
    with pytest.raises(ValueError):
        runner.run_tests([path], URL, "synthetic@password")


def test_real_test_subprocess_output_is_redacted(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    original = subprocess.Popen

    def start(command: list[str], **kwargs: object) -> subprocess.Popen[str]:
        assert URL not in " ".join(command)
        assert "--showlocals" not in command
        assert "-v" in command and "--durations=15" in command
        assert "--careflow-timings" in command
        # Replace only the test executable with a synthetic failing child.
        return original(  # type: ignore[call-overload,no-any-return]
            [
                sys.executable,
                "-c",
                "import os,sys; print(os.environ['TEST_DATABASE_URL']); "
                "print('synthetic@password'); sys.exit(7)",
            ],
            **kwargs,
        )

    monkeypatch.setattr(subprocess, "Popen", start)
    assert runner.run_tests([], URL, "synthetic@password") == 7
    output = capsys.readouterr()
    assert "synthetic" not in output.out + output.err
    assert "redacted" in output.out


def test_temp_preflight_fails_before_database_access(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("TEST_DATABASE_URL", URL)
    monkeypatch.setattr(sys, "argv", ["runner", "test"])
    calls: list[str] = []

    def inaccessible(path: Path) -> None:
        raise RuntimeError(
            "Private pytest temporary-directory access failed. "
            "Use normal-host execution."
        )

    def catalog(url: str) -> set[str]:
        calls.append("catalog")
        return set()

    monkeypatch.setattr(runner, "check_private_temp", inaccessible)
    monkeypatch.setattr(runner, "disposable_names", catalog)
    assert runner.main() == 1
    assert calls == []
    assert "normal-host" in capsys.readouterr().out


def test_runner_checks_cleanup_on_failed_tests(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("TEST_DATABASE_URL", URL)
    monkeypatch.setattr(sys, "argv", ["runner", "test"])
    catalogs = iter([set(), {"careflow_test_synthetic"}])
    monkeypatch.setattr(runner, "disposable_names", lambda url: next(catalogs))
    monkeypatch.setattr(runner, "run_tests", lambda *args: 2)
    assert runner.main() == 1
    assert "cleanup incomplete" in capsys.readouterr().out


@pytest.mark.skipif(sys.platform != "win32", reason="Windows DPAPI and ACL tests")
@pytest.mark.parametrize("shell", ["powershell", "pwsh"])
def test_windows_lifecycle_and_process_environment(shell: str) -> None:
    executable = shutil.which(shell)
    if not executable:
        pytest.skip(f"{shell} not installed")
    # Real DPAPI, ACLs and subprocess launch; fake validation server, synthetic data.
    # Outside the checkout, with guaranteed deletion on success/failure.
    with tempfile.TemporaryDirectory(prefix="careflow-credential-test-") as temporary:
        root = Path(temporary)
        scripts = root / "scripts"
        scripts.mkdir()
        source = (runner.ROOT / "scripts/postgres-tests.ps1").read_text()
        source = source.replace(
            "$python = Join-Path $root '.venv\\Scripts\\python.exe'",
            "$python = '" + sys.executable.replace("'", "''") + "'",
        )
        (scripts / "postgres-tests.ps1").write_text(source)
        (scripts / "postgres_test_runner.py").write_text(
            "import os,sys\n"
            "from urllib.parse import unquote\n"
            "u=os.environ['TEST_DATABASE_URL']\n"
            "assert u.startswith('postgresql+psycopg://postgres:')\n"
            "assert u.endswith('@127.0.0.1:5432/postgres')\n"
            "assert all(u not in arg for arg in sys.argv)\n"
            "assert 'DATABASE_URL' not in os.environ\n"
            "assert 'PGPASSWORD' not in os.environ\n"
            "assert 'ANTHROPIC_API_KEY' not in os.environ\n"
            "print('Synthetic helper stdout received.')\n"
            "sys.stderr.write('synthetic@password')\n"
            "sys.exit(1 if 'wrong' in unquote(u) else 0)\n"
        )
        check = r"""
$ErrorActionPreference = 'Stop'
. ./scripts/postgres-tests.ps1
function Get-CredentialDirectory { Join-Path (Get-Location) 'private' }
$script:promptCount = 0
$script:secret = 'synthetic@password'
function Read-Host { param($Prompt, [switch]$AsSecureString)
    if (-not $AsSecureString) { throw 'Prompt must be secure' }
    $script:promptCount++
    ConvertTo-SecureString $script:secret -AsPlainText -Force
}
function ExpectFailure($Operation) {
    $failed = $false
    try { & $Operation | Out-Null } catch { $failed = $true }
    if (-not $failed) { throw 'Expected rejection' }
}
$env:DATABASE_URL = 'parent-sentinel'
$env:TEST_DATABASE_URL = 'parent-sentinel'
$env:PGPASSWORD = 'parent-sentinel'
$env:ANTHROPIC_API_KEY = 'parent-sentinel'
ExpectFailure { Invoke-PostgresTests validate @() }
if ((Invoke-PostgresTests setup @()) -ne 0) { throw 'Setup failed' }
$file = Join-Path (Get-CredentialDirectory) 'credential.clixml'
if ((Get-Content -Raw $file).Contains($script:secret)) { throw 'Plaintext persisted' }
Assert-PrivateAcl (Get-CredentialDirectory)
Assert-PrivateAcl $file
if ((Invoke-PostgresTests validate @()) -ne 0) { throw 'Reuse failed' }
if ((Invoke-PostgresTests test @('backend/integration_tests')) -ne 0) {
    throw 'Launch failed'
}
if ($script:promptCount -ne 1) { throw 'Reuse prompted' }
ExpectFailure { Invoke-PostgresTests setup @() }
ExpectFailure { Invoke-PostgresTests test @('--showlocals') }
$original = [IO.File]::ReadAllText($file)
$script:secret = 'wrong'
if ((Invoke-PostgresTests rotate @()) -eq 0) { throw 'Invalid accepted' }
if ([IO.File]::ReadAllText($file) -cne $original) { throw 'Failed rotation lost file' }
$script:secret = 'rotated@synthetic'
if ((Invoke-PostgresTests rotate @()) -ne 0) { throw 'Rotation failed' }
$stored = Import-Clixml $file
if ($stored.GetNetworkCredential().Password -cne $script:secret) {
    throw 'Rotation not saved'
}
$stored.Password.Dispose()
if ((Invoke-PostgresTests validate @()) -ne 0) { throw 'Rotated reuse failed' }
icacls $file /grant '*S-1-1-0:R' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Synthetic ACL broadening failed' }
ExpectFailure { Invoke-PostgresTests validate @() }
Set-PrivateAcl $file $false
Set-Content $file 'corrupt synthetic XML'
ExpectFailure { Invoke-PostgresTests validate @() }
if ((Invoke-PostgresTests delete @()) -ne 0) { throw 'Delete failed' }
if (Test-Path $file) { throw 'File remains' }
if ((Invoke-PostgresTests delete @()) -ne 0) { throw 'Repeated delete failed' }
ExpectFailure { Invoke-PostgresTests validate @() }
$names = @('DATABASE_URL', 'TEST_DATABASE_URL', 'PGPASSWORD', 'ANTHROPIC_API_KEY')
foreach ($name in $names) {
    if ([Environment]::GetEnvironmentVariable($name) -cne 'parent-sentinel') {
        throw 'Parent environment changed'
    }
}
Write-Host 'Lifecycle and subprocess isolation passed.'
"""
        (root / "check.ps1").write_text(check)
        result = subprocess.run(
            [
                executable,
                "-NoProfile",
                "-NonInteractive",
                "-File",
                str(root / "check.ps1"),
            ],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=90,
            env={
                key: value
                for key, value in os.environ.items()
                if key.upper() != "PSMODULEPATH"
            },
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "Lifecycle and subprocess isolation passed." in result.stdout
        assert "Synthetic helper stdout received." in result.stdout
        assert "synthetic@password" not in result.stdout + result.stderr
