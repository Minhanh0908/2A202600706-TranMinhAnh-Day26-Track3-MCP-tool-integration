from __future__ import annotations

import json
from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ResourceError, ToolError

try:
    from .db import DEFAULT_DB_PATH, SQLiteAdapter, ValidationError
    from .init_db import create_database
except ImportError:
    from db import DEFAULT_DB_PATH, SQLiteAdapter, ValidationError
    from init_db import create_database


if not DEFAULT_DB_PATH.exists():
    create_database(DEFAULT_DB_PATH)

adapter = SQLiteAdapter(DEFAULT_DB_PATH)
mcp = FastMCP("SQLite Lab MCP Server")


@mcp.tool(name="search")
def search(
    table: str,
    filters: dict[str, Any] | list[dict[str, Any]] | None = None,
    columns: list[str] | None = None,
    limit: int = 20,
    offset: int = 0,
    order_by: str | None = None,
    descending: bool = False,
) -> dict[str, Any]:
    """Search rows from a validated SQLite table with filters, ordering, and pagination."""
    try:
        return adapter.search(
            table=table,
            filters=filters,
            columns=columns,
            limit=limit,
            offset=offset,
            order_by=order_by,
            descending=descending,
        )
    except ValidationError as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool(name="insert")
def insert(table: str, values: dict[str, Any]) -> dict[str, Any]:
    """Insert one row into a validated SQLite table and return the inserted row."""
    try:
        return adapter.insert(table=table, values=values)
    except ValidationError as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool(name="aggregate")
def aggregate(
    table: str,
    metric: str,
    column: str | None = None,
    filters: dict[str, Any] | list[dict[str, Any]] | None = None,
    group_by: str | None = None,
) -> dict[str, Any]:
    """Aggregate rows using count, avg, sum, min, or max with optional filters and grouping."""
    try:
        return adapter.aggregate(
            table=table,
            metric=metric,
            column=column,
            filters=filters,
            group_by=group_by,
        )
    except ValidationError as exc:
        raise ToolError(str(exc)) from exc


@mcp.resource("schema://database")
def database_schema() -> str:
    """Return the complete database schema as JSON text."""
    return json.dumps(adapter.get_database_schema(), indent=2)


@mcp.resource("schema://table/{table_name}")
def table_schema(table_name: str) -> str:
    """Return one table schema as JSON text."""
    try:
        return json.dumps(adapter.get_table_schema(table_name), indent=2)
    except ValidationError as exc:
        raise ResourceError(str(exc)) from exc


if __name__ == "__main__":
    try:
        mcp.run()
    except ValidationError:
        raise
