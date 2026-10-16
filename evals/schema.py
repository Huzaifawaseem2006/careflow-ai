"""Validate the versioned synthetic case contract before producing any result."""

import hashlib
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Text = Annotated[str, Field(min_length=1, pattern=r"\S")]
Partition = Literal["dev", "held-out"]
Category = Literal[
    "positive",
    "negative",
    "adversarial",
    "missing-evidence",
    "tool-misuse",
    "privacy",
    "escalation",
]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Turn(Contract):
    role: Literal["user", "assistant"]
    content: Text


class Expectations(Contract):
    required_tools: list[Text]
    forbidden_tools: list[Text]
    source_ids: list[Text]
    abstain: bool
    state_assertions: Annotated[list[Text], Field(min_length=1)]
    response_assertions: Annotated[list[Text], Field(min_length=1)]

    @model_validator(mode="after")
    def consistent(self) -> Self:
        for values in (self.required_tools, self.forbidden_tools, self.source_ids):
            if len(values) != len(set(values)):
                raise ValueError("Duplicate expectation")
        if set(self.required_tools) & set(self.forbidden_tools):
            raise ValueError("Required and forbidden tools overlap")
        if self.abstain and self.source_ids:
            raise ValueError("Abstention cannot require citations")
        return self


class Case(Contract):
    id: Annotated[str, Field(pattern=r"^CF-EVAL-[0-9]{3}$")]
    category: Category
    group: Text
    turns: Annotated[list[Turn], Field(min_length=1)]
    synthetic: Literal[True]
    clinic_fixture: Literal["00000000-0000-4000-8000-000000000001"]
    # Persona references are scenarios, never authenticated account identities.
    actor_fixture: Literal["guest", "00000000-0000-4000-8000-000000000011"]
    corpus_version: Text | None
    expected: Expectations
    severity: Literal["normal", "high", "critical"]
    partition: Partition
    provenance: Text


class Manifest(Contract):
    schema_version: Literal["1"]
    dataset_version: Text
    cases_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    fixture_version: Literal["ticket04-v1"]


def load_dataset(directory: Path) -> tuple[Manifest, list[Case]]:
    manifest = Manifest.model_validate_json((directory / "manifest.json").read_bytes())
    data = (directory / "cases.jsonl").read_bytes()
    if hashlib.sha256(data).hexdigest() != manifest.cases_sha256:
        raise ValueError("Dataset checksum mismatch; version and review changes")
    cases = [Case.model_validate_json(line) for line in data.splitlines()]
    if not cases:
        raise ValueError("Empty dataset")
    if len({case.id for case in cases}) != len(cases):
        raise ValueError("Duplicate case ID")
    return manifest, cases
