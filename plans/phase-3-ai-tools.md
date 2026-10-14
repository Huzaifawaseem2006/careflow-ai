# Phase 3 — AI tools

Entry: Phase 2 gate passes. Phase 1 has already established versioned synthetic cases and harness infrastructure. Before agent behavior, wire that harness to the real orchestrator path with a mocked provider boundary and validate case grading. Decide D07 and confirm provider API/tool schema capabilities from official docs against pinned SDK/model.

Slice 1: bounded explicit tool loop with structured outputs and read-only doctor/slot/fee/owned-appointment adapters. Slice 2: proposal adapters. Slice 3: confirmed writes driven only by server-verified user confirmation. Each tool has typed, versioned input/output and a service authorization check. Reject unauthorized calls, malformed output, runaway loops and ambiguous retries. Provider errors must not produce a success claim.

For each slice run format/lint/type/unit/integration checks and targeted adversarial/positive eval cases; compare to the prior baseline. Label mocked vs live runs separately. If credentials/network/budget block live runs, record blocked status. Phase exit requires full applicable regression and no critical auth, booking or safety failures.
