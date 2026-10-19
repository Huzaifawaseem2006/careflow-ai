"""Durable, serial paid-evaluation accounting. Never used by ordinary chat or CI."""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4

CEILING = 5_000_000  # Integer millionths of USD; never floating-point money.


class BudgetBlocked(ValueError):
    """Safe marker; an unresolved reservation requires operator reconciliation."""


def micros(value: str) -> int:
    try:
        amount = Decimal(value)
        scaled = amount * 1_000_000
        if not amount.is_finite() or scaled < 0 or scaled != scaled.to_integral():
            raise BudgetBlocked("Invalid USD amount")
        return int(scaled)
    except (InvalidOperation, ValueError, OverflowError):
        raise BudgetBlocked("Invalid USD amount") from None


def dollars(value: int) -> str:
    return format(Decimal(value) / 1_000_000, ".6f")


class Ledger:
    def __init__(self, path: Path) -> None:
        self.path = path
        if not path.is_file():
            raise BudgetBlocked("Missing cumulative ledger")

    @classmethod
    def initialize(
        cls, path: Path, *, previous_spend_usd: str, evidence: str
    ) -> "Ledger":
        previous = micros(previous_spend_usd)
        if previous > CEILING or not evidence.strip():
            raise BudgetBlocked("Previous spend requires evidence within the ceiling")
        path.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation prevents resetting a previous ledger accidentally.
        with path.open("xb"):
            pass
        with sqlite3.connect(path) as db:
            db.executescript("""
                CREATE TABLE baseline (spent INTEGER NOT NULL, evidence TEXT NOT NULL);
                CREATE TABLE runs (id TEXT PRIMARY KEY, model TEXT NOT NULL,
                    dataset TEXT NOT NULL, cases TEXT NOT NULL,
                    maximum INTEGER NOT NULL,
                    approval TEXT NOT NULL);
                CREATE TABLE calls (id TEXT PRIMARY KEY, run TEXT NOT NULL,
                    case_id TEXT NOT NULL, reserved INTEGER NOT NULL, charged INTEGER,
                    usage TEXT, created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            """)
            db.execute("INSERT INTO baseline VALUES (?, ?)", (previous, evidence))
        return cls(path)

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        try:
            with sqlite3.connect(self.path, timeout=10) as db:
                db.execute("PRAGMA synchronous=FULL")
                db.execute("BEGIN IMMEDIATE")
                yield db
        except sqlite3.Error:
            raise BudgetBlocked("Cumulative ledger unavailable") from None

    def start_run(
        self,
        identifier: str,
        *,
        model: str,
        dataset: str,
        cases: list[str],
        maximum_usd: str,
        approval: str,
    ) -> None:
        maximum = micros(maximum_usd)
        if (
            not all((identifier, model, dataset, approval.strip(), cases))
            or not 0 < maximum <= CEILING
        ):
            raise BudgetBlocked("Explicit bounded run approval required")
        if len(cases) != len(set(cases)):
            raise BudgetBlocked("Duplicate approved case")
        with self.transaction() as db:
            db.execute(
                "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?)",
                (identifier, model, dataset, json.dumps(cases), maximum, approval),
            )

    def reserve(self, run: str, case: str, maximum_usd: str) -> str:
        amount = micros(maximum_usd)
        with self.transaction() as db:
            approved = db.execute(
                "SELECT cases, maximum FROM runs WHERE id=?", (run,)
            ).fetchone()
            if approved is None or case not in json.loads(approved[0]) or amount <= 0:
                raise BudgetBlocked("Unapproved dispatch")
            if db.execute("SELECT 1 FROM calls WHERE charged IS NULL").fetchone():
                raise BudgetBlocked("Unresolved or concurrent charged call")
            previous = db.execute("SELECT spent FROM baseline").fetchone()
            if previous is None:
                raise BudgetBlocked("Unknown prior spend")
            total = db.execute("SELECT coalesce(sum(charged),0) FROM calls").fetchone()[
                0
            ]
            run_total = db.execute(
                "SELECT coalesce(sum(charged),0) FROM calls WHERE run=?", (run,)
            ).fetchone()[0]
            if (
                previous[0] + total + amount > CEILING
                or run_total + amount > approved[1]
            ):
                raise BudgetBlocked("Insufficient conservative remaining budget")
            identifier = uuid4().hex
            db.execute(
                "INSERT INTO calls (id,run,case_id,reserved) VALUES (?,?,?,?)",
                (identifier, run, case, amount),
            )
        return identifier

    def settle(
        self, reservation: str, *, input_tokens: int, output_tokens: int
    ) -> None:
        # $4/M counts ALL input at the most expensive supported cache-write rate.
        # This is a conservative charge bound, not an invoice or exact actual cost.
        if (
            type(input_tokens) is not int
            or type(output_tokens) is not int
            or min(input_tokens, output_tokens) < 0
        ):
            raise BudgetBlocked("Unknown reported usage")
        charge = input_tokens * 4 + output_tokens * 10
        with self.transaction() as db:
            row = db.execute(
                "SELECT reserved, charged FROM calls WHERE id=?", (reservation,)
            ).fetchone()
            if row is None or row[1] is not None or charge > row[0]:
                raise BudgetBlocked("Usage exceeds reservation or is ambiguous")
            db.execute(
                "UPDATE calls SET charged=?,usage=? WHERE id=?",
                (
                    charge,
                    json.dumps(
                        {"input_tokens": input_tokens, "output_tokens": output_tokens}
                    ),
                    reservation,
                ),
            )

    def summary(self) -> dict[str, object]:
        with self.transaction() as db:
            previous = db.execute("SELECT spent FROM baseline").fetchone()[0]
            charged, reserved = db.execute(
                "SELECT coalesce(sum(charged),0), "
                "coalesce(sum(CASE WHEN charged IS NULL THEN reserved "
                "ELSE 0 END),0) FROM calls"
            ).fetchone()
        return {
            "previous_spend_usd": dollars(previous),
            "charged_upper_usd": dollars(charged),
            "reserved_usd": dollars(reserved),
            "remaining_lower_usd": dollars(CEILING - previous - charged - reserved),
            "actual_cost_usd": None,
        }
