"""Strict read-only tools over existing authoritative catalog services."""

import json
from typing import Annotated
from uuid import UUID

from pydantic import Field

from careflow.catalog import CatalogKind, catalog_connection, read_catalog
from careflow.chat_contracts import (
    Contract,
    DoctorFact,
    ServiceFact,
    SpecialtyFact,
    ToolCall,
    ToolDefinition,
    ToolResult,
)

QueryText = Annotated[str, Field(min_length=1, max_length=120, pattern=r"\S")]


class SearchArguments(Contract):
    query: QueryText | None
    resource_id: UUID | None
    city: Annotated[str, Field(min_length=1, max_length=80)] | None
    limit: int = Field(ge=1, le=20)
    offset: int = Field(ge=0, le=10000)


class DoctorArguments(SearchArguments):
    specialty_id: UUID | None


class FeeArguments(Contract):
    resource_id: UUID


ARGUMENTS: dict[str, type[SearchArguments] | type[FeeArguments]] = {
    "search_doctors": DoctorArguments,
    "search_specialties": SearchArguments,
    "search_services": SearchArguments,
    "get_consultation_fee": FeeArguments,
    "get_service_fee": FeeArguments,
}
KINDS: dict[str, CatalogKind] = {
    "search_doctors": "doctors",
    "get_consultation_fee": "doctors",
    "search_specialties": "specialties",
    "search_services": "services",
    "get_service_fee": "services",
}
TOOLS = tuple(
    ToolDefinition(
        name=name,
        description=(
            "Read active fictional-clinic " + KINDS[name] + ". "
            "Consultation fees belong to doctors; service fees are independent. "
            "No availability or policy evidence. Query filters this bounded page only; "
            "empty/multiple matches require clarification. "
            "Never infer a service-doctor association."
        ),
        schema_=model.model_json_schema(),
    )
    for name, model in ARGUMENTS.items()
)


def validate_call(call: ToolCall) -> SearchArguments | FeeArguments:
    # JSON strict mode accepts UUID strings but never coerces booleans/numbers.
    return ARGUMENTS[call.name].model_validate_json(
        json.dumps(call.arguments), strict=True
    )


def execute_catalog(call: ToolCall) -> ToolResult:
    arguments = validate_call(call)
    filters = arguments.model_dump(exclude={"query"})
    with catalog_connection() as connection:
        rows = read_catalog(connection, KINDS[call.name], **filters)
    query = arguments.query if isinstance(arguments, SearchArguments) else None
    if query is not None:
        rows = [
            row
            for row in rows
            if query.casefold().strip() in str(row["name"]).casefold()
        ]
    models: dict[str, type[SpecialtyFact]] = {
        "doctors": DoctorFact,
        "services": ServiceFact,
        "specialties": SpecialtyFact,
    }
    model = models[KINDS[call.name]]
    return ToolResult(
        name=call.name,
        status=("ambiguous" if query is not None and len(rows) > 1 else "ok")
        if rows
        else "empty",
        data=[model.model_validate(row) for row in rows],
        limit=arguments.limit if isinstance(arguments, SearchArguments) else 1,
        offset=arguments.offset if isinstance(arguments, SearchArguments) else 0,
    )
