# Phase 3 evaluation gate

Ticket 06 implementation is authorized. Owner subsequently authorized one scoped
commit/push after independent review and required local verification pass. Live
calls remain explicitly prohibited for this publication task. Combined Phase 3
exit remains blocked until every documented gate passes.

## Frozen cases and real paths

`evals/phase3_v1` freezes 32 synthetic cases (23 held-out, nine development),
SHA-256 `d1719bea7939f7a68341c1ab44d0ed098cc987ffa6d5a6ccd67e4842bd5a64ff`.
Cases contain required/forbidden tools, personas, severity, partitions, review/
confirmation intent and state/response assertions. LF checkout preserves bytes.
Held-out cases were frozen before implementation/evaluation; the prompt is unchanged.

Both modes use identical HTTPS-scheme in-process ASGI, conversations, orchestrator,
tools, domain services, PostgreSQL snapshots and deterministic graders. Only the
external provider differs: scripted replies or the existing Anthropic adapter.
This is a backend walkthrough, not deployed TLS/frontend verification. Each case
uses a fresh migrated `template0` disposable DB, real catalog/generated slots,
foreign-clinic distractor, provisioned/authenticated patient accounts and an initial
appointment. Reports map personas to actual disposable user/patient IDs.

Independent catalog facts and earlier cancellation/rescheduling state/audit
oracles are reused. The harness separately confirms through authenticated
same-origin CSRF endpoints; the model cannot confirm. Checks cover grounding,
ownership, context, review exactness, unconfirmed state, replay, stale fee/slot/
appointment, cutoff, provider errors and failure after commit. No real data is used.

```powershell
powershell.exe -NoProfile -File scripts/postgres-tests.ps1 test -TestPath backend/integration_tests/test_phase3_gate_integration.py
powershell.exe -NoProfile -File scripts/postgres-tests.ps1 test
.venv/Scripts/python -m evals.phase3_gate --combine-mocked --report test-results/ticket06-mocked-all.json
```

Individual reports are `test-results/ticket06-mocked-P3-*.json`. Combining requires
every frozen case exactly once with matching current source, dataset, default config,
installed SDK, prompt/tool versions and mocked mode. The source fingerprint includes
application/evaluation Python, migration Python, `pyproject.toml`, `alembic.ini` and
the Python-version pin. Incompatible/stale evidence is rejected.
Event journals preserve completed observations on interruption; retain failed
attempts and use new console/JUnit names. The existing credential runner remains
the only credential-delivery path. Its DPAPI credential remains outside Git.

Four `--control` modes must exit 1: `wrong-tool`, `fabricated-success`, `cross-user`
and `unconfirmed-mutation`. Cross-user control deliberately corrupts a response;
unconfirmed mutation actually commits in the disposable DB without the case's
confirmation event. These test grader sensitivity, not production vulnerabilities.
No live fault injection is allowed. Exit 2 means blocked/incomplete, never passed.
Live mode also returns exit 2 when individual cases pass but held-out model-quality
coverage remains blocked. Focused mocked runs retain their case-only exit behavior.
Both modes reject invalid or nondefault effective `CHAT_*` limits before database
or provider execution, so inherited overrides cannot change the approved evaluation
configuration. Configuration is null when that validation fails.

Safe reports include revision/dirty/source hash, SDK/requested/resolved model,
config/prompt/tool/dataset/fixture versions, case statuses, failed checks, safe tool
names, actor mapping, latency samples and available reported usage. Unknown metrics
remain null. Earlier baselines are catalog 13 passed/2 pending, context 8, booking
8, cancellation 8, rescheduling 10. Full PostgreSQL regression reruns them; earlier
pending catalog inventory cases are not converted to passes by this new dataset.

## Durable budget and live entry

Retain ignored `evals/results/phase3-spend.sqlite` across sessions. Initial prior
spend is USD 0, supported by Tickets 01–05/current no-paid-call evidence. Never
delete/reinitialize it to regain budget. Exclusive initialization and SQLite
immediate transactions prevent reset/concurrent reservations. Each run records a
unique owner approval reference, model, checksum, exact case IDs and cost maximum.
Approval files record human authorization; creating one or holding a key does not
authorize spending. Reusing a run ID fails closed.

Reserve each call's full configured UTF-8 context bound as tokens plus 16,384
protocol tokens at USD 4/M and maximum output including thinking at USD 10/M.
The adapter independently bounds system/schema/history bytes. Default reservation:
**USD 0.267776/call**. USD 4/M covers the highest documented input cache-write rate;
base input is USD 2/M. Settle reported aggregate input including caches and output
including thinking at these conservative rates. Actual invoice cost remains null;
reported usage, estimates and upper charges are separate. Both the approved run
maximum and cumulative **USD 5** ceiling apply.

Unknown/stale pricing or usage, model substitution, transport/protocol failure,
interruption, outstanding reservations and insufficient budget stop dispatch.
Ambiguous calls retain reservations pending explicit billing reconciliation, with
no automatic release/retry. SDK retries remain zero; no fallback model or paid CI.
All remaining requested cases become blocked if a limit is reached. Fixed UTC
pricing-date checks require fresh verification before any later date's paid run.

Use only server-process `ANTHROPIC_API_KEY` and intentional `CHAT_ENABLED=true`;
there is no implicit `.env` load. Never paste keys in chat, commands, reports or
tracked files. The existing official-host/no-proxy/no-redirect client suppresses
SDK body logging/telemetry. Reports omit messages, provider bodies, cookies, CSRF,
proofs, retry keys and thinking. Only minimal synthetic context/static schemas
reach Anthropic. Local disposable history is dropped; spend metadata persists.

```powershell
.venv/Scripts/python -m evals.phase3_gate --probe-model --report test-results/ticket06-model-access.json
```

This read-only Models API probe never sends Messages. Live entry repeats it after
approval/config validation. Published model availability does not prove account
access/credits. Missing key/network/access/credits remains blocked evidence.

## Proposed first live run — approval pending

- Model: **claude-sonnet-5-5**, default application limits and unchanged prompt/tools.
- Cases: **P3-001 through P3-023**, checksum above, one attempt each, no automatic
  reruns or tuning. At most **120 Messages calls**, including context setup;
  existing per-turn caps apply.
- Proposed maximum: **USD 4.50**, inside the cumulative USD 5 ceiling with zero
  prior spend. Rough estimate: 200,000–450,000 input and 20,000–60,000 output
  tokens, about USD 0.60–1.50 at base prices. These are unmeasured planning estimates.
  Conservative reservations can stop the run early; completing blocked cases
  never authorizes extra spend.
- Prerequisites: applicable offline/regression gates pass; explicit owner approval
  of model/cases/cost; server key; account model access; retention disclosure.
  Model changes and additional paid runs require new approval/evaluation.
- Gate: actual held-out model-observed tool selection >=95%, all critical/auth/
  state/safety checks pass, complete requested coverage. The combined executable
  case gate also requires zero failed deterministic cases. Report numerator,
  denominator, repeats and Wilson 95% interval; this small correlated sample does
  not establish population accuracy. P3-021 is backend-only ownership rejection:
  mandatory for safety but excluded from model quality. There are **22 eligible
  model cases and one backend-only case**. Development, backend-only, partial and
  zero-observation runs cannot pass the held-out quality gate. Scripted metrics
  stay null; no LLM judge replaces auth/state assertions. FAQ/citations are Phase 4.

Anthropic commercial API inputs/outputs normally expire within 30 days, with
contractual, service, usage-policy and legal exceptions. Compiled strict schemas
may be cached. Account ZDR/terms are unverified; local deletion cannot delete
provider copies. Covered-model rules may differ. Approval must acknowledge these
boundaries. Sources verified **2026-10-19**:
[active model/pricing](https://platform.claude.com/docs/en/models/sonnet-5-5/overview),
[commercial retention](https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data),
[covered models](https://privacy.claude.com/en/articles/15425996-data-retention-practices-for-covered-models).

After approval, record its actual owner reference, model, checksum, all 23 IDs,
default `Limits` config, USD 4.50/120-call maxima, pricing date and confirmed
retention/access in an ignored JSON `Approval` record. No credentials belong in
it. Save this record at `evals/results/phase3-live-approval.json`, then use the
credential-isolated fixed entry point:

```powershell
powershell.exe -NoProfile -File scripts/postgres-tests.ps1 phase3-eval
```

This command reuses the saved DPAPI database credential without exporting it to
the parent shell. Only this explicit local operation preserves the server API key
for the evaluation child. It accepts no test selectors or arbitrary CLI options,
rejects CI, uses the fixed held-out partition/approval/ledger, redacts both secrets
from console output and verifies disposable database cleanup. Each invocation
writes a new ignored `test-results/phase3-live-<UUID>.json` report. The approval
record and all model/budget/access/retention gates still apply before Messages.

## Remaining gates

Executed results/failures belong in [PROGRESS](PROGRESS.md). Live quality and the
combined Phase 3 exit remain blocked without approved live evidence. D01/D11 exact
wording/named reviewer remain separate release approvals. Hosted Actions for the
eventual exact Ticket 06 commit are checked after the owner-authorized publication;
passing Actions at `78f3f3e` support entry only. No next-phase work is authorized.
