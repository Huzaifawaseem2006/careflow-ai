# Local PostgreSQL test credentials (Windows)

Run from the CareFlow AI checkout with the pinned `.venv` dependencies installed.
The runner is `scripts/postgres-tests.ps1`; Windows PowerShell 5.1 and PowerShell 7
are supported. It uses the existing native PostgreSQL installation, with no Docker
or additional dependencies. The endpoint is fixed to `127.0.0.1:5432`, login
`postgres`, maintenance database `postgres`. There is no arbitrary URL/host option.

## Commands

One-time setup, in an interactive PowerShell terminal under your Windows account:

```powershell
powershell.exe -NoProfile -File .\scripts\postgres-tests.ps1 setup
```

Enter the local PostgreSQL password at `Read-Host -AsSecureString`. It is not echoed
or placed in command history. Setup validates connectivity before saving. Existing
credentials are not overwritten by `setup`. Do not paste the password into chat.
If local execution policy blocks this checked-out script, add
`-ExecutionPolicy Bypass` before `-File` for this invocation only; no persistent
policy change is needed.

```powershell
# Check saved credentials; no password prompt or database changes.
powershell.exe -NoProfile -File .\scripts\postgres-tests.ps1 validate

# Run all PostgreSQL integration tests; reuse without prompting.
powershell.exe -NoProfile -File .\scripts\postgres-tests.ps1 test

# Or select an integration file or an individual test function.
powershell.exe -NoProfile -File .\scripts\postgres-tests.ps1 test -TestPath backend/integration_tests/test_database_integration.py
powershell.exe -NoProfile -File .\scripts\postgres-tests.ps1 test -TestPath backend/integration_tests/test_database_integration.py::test_unmigrated_database_is_not_ready_but_process_is_alive

# Prompt for an updated password and atomically replace the local encrypted copy.
powershell.exe -NoProfile -File .\scripts\postgres-tests.ps1 rotate

# Delete only the saved credential; safe to repeat.
powershell.exe -NoProfile -File .\scripts\postgres-tests.ps1 delete
```

Rotation updates the saved copy of an already changed PostgreSQL password. It does
not change the server password. Failed validation leaves the previous file intact.
Deletion does not change the server, revoke credentials, or securely erase backups.
The empty private configuration directory remains. Keep the credential between
Codex sessions unless you explicitly want to remove it.

## Storage and access

The credential is a `PSCredential` exported using Windows `Export-Clixml` at:

```text
%USERPROFILE%\.careflow-ai\credential.clixml
C:\Users\USER\.careflow-ai\credential.clixml
```

Only the password is DPAPI-encrypted; the username and XML metadata are not secret.
`Import-Clixml` requires the same Windows user on the same computer. The directory
and file have protected ACLs granting only the current account full control, with
that account as owner. Validation/test reject unexpected owners, inherited or extra
rules, corrupt credentials and reparse points. Rotation/setup apply private ACLs;
no administrator or audit-policy privilege is required. Do not sync or copy the
file into the checkout, `.env`, shell profiles or another machine. A different
account/machine needs its own setup. Administrative takeover and programs already
running as your account remain outside this protection boundary.

PowerShell decrypts only while starting the helper, builds a percent-encoded URL
in memory and passes `TEST_DATABASE_URL` through `ProcessStartInfo`'s child
environment. It clears that environment entry and frees the temporary BSTR after
launch. Managed string copies cannot be reliably zeroed. The calling shell's
environment is never changed. Python removes the URL from its own environment,
checks the fixed target before connecting, and supplies it to the pytest process.
Inherited `DATABASE_URL`, `PG*`, pytest injection variables and `ANTHROPIC_API_KEY`
are removed from the child environment. Plugin autoload is disabled. Secret values
never enter command arguments. Use a trusted checkout; test code and other programs
running as the same user can access subprocess memory/environment. Run without
debuggers, tracing or memory dumps when using a real credential.

## Database safety and output

Validation performs read-only queries against `postgres` and its database catalog.
Test fixtures are unchanged: every test creates/drops a unique
`careflow_test_<32 hex>` database. The runner never connects to `careflow_ai`.
The suite requires CREATEDB and extension-install privileges; identity tests also
create/remove a temporary login role and require CREATEROLE. Validation proves
connectivity, not all these permissions or extension availability.

Run serially in an idle checkout; do not overlap database runs with each other,
CI subprocess regressions, other checks or source edits. Use `-TestPath` during
implementation and the full integration suite when required by the final task
gate. A failed run needs diagnosis before retrying; inspect its exit status and
cleanup evidence, and preserve all target/teardown checks when rerunning.
The runner compares disposable database names
before/after and returns failure if new leftovers remain; it never deletes them
on its own. Existing leftovers are not removed or certified clean. The fixture's
own teardown verifies each database drop. Forced process termination can prevent
teardown; inspect only `careflow_test_*` resources manually before retrying.

Only integration-test paths/functions are accepted, with fixed pytest options.
Raw SQL, custom executables, arbitrary pytest flags and phase-gate entry points
are not exposed. Historical phase-gate launchers are separate; this runner does
not export credentials for them. It supplies no application configuration.

Native/connection failures return generic messages without exception details.
Test stdout/stderr are piped through URL/password redaction before display; no
raw output/JUnit files are written by this runner. Fresh pytest temporaries live
under ignored `test-results/postgres-<UUID>`. Do not add tests that write secrets
to files or transform them for display; output filtering is defense in depth for
trusted tests, not a sandbox for malicious code. Do not enable `--showlocals`,
transcripts or raw diagnostic dumps. No model API calls are needed.

Missing, invalid, corrupt or inaccessible credentials fail without a password
prompt; Codex should report the condition and ask the owner to run `setup` or
`rotate` interactively. Never inspect/decrypt the saved credential for diagnosis.
For WinError 5 from restricted Windows temp access, run the same command from
ordinary local PowerShell or use authorized normal-host execution.

## Tooling verification

```powershell
.venv\Scripts\python -m pytest backend/tests/test_postgres_tooling.py -q -p no:cacheprovider
.venv\Scripts\python -m ruff format --check backend scripts ci_tests evals
.venv\Scripts\python -m ruff check backend scripts ci_tests evals
.venv\Scripts\python -m mypy backend scripts ci_tests evals
```

The Windows lifecycle tests use temporary synthetic credentials outside the
checkout and a fake validation server, exercising real DPAPI, ACLs, atomic
replacement and subprocess environments on both installed PowerShell versions.
They do not change the saved real credential or prove live PostgreSQL acceptance.
Non-Windows hosts skip these Windows-only checks; the portable safety checks run.
