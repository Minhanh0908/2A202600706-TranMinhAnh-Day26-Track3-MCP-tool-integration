from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from implementation.db import SQLiteAdapter, ValidationError
from implementation.init_db import create_database


@pytest.fixture()
def adapter(tmp_path: Path) -> SQLiteAdapter:
    db_path = tmp_path / "lab.db"
    create_database(db_path)
    return SQLiteAdapter(db_path)


def test_search_filters_ordering_and_pagination(adapter: SQLiteAdapter) -> None:
    result = adapter.search(
        table="students",
        filters={"cohort": "A1"},
        columns=["name", "score"],
        order_by="score",
        descending=True,
        limit=1,
    )

    assert result["count"] == 1
    assert result["rows"][0]["name"] == "Binh Tran"


def test_insert_returns_inserted_row(adapter: SQLiteAdapter) -> None:
    result = adapter.insert(
        "students",
        {
            "name": "Minh Anh",
            "email": "minh.anh@example.edu",
            "cohort": "A2",
            "score": 86.0,
        },
    )

    assert result["inserted_id"]
    assert result["row"]["email"] == "minh.anh@example.edu"


def test_aggregate_average_by_group(adapter: SQLiteAdapter) -> None:
    result = adapter.aggregate("students", "avg", column="score", group_by="cohort")

    cohorts = {row["cohort"]: row["value"] for row in result["rows"]}
    assert pytest.approx(cohorts["A1"]) == 90.25


def test_database_and_table_schema(adapter: SQLiteAdapter) -> None:
    database_schema = adapter.get_database_schema()
    table_schema = adapter.get_table_schema("students")

    assert set(database_schema["tables"]) == {"courses", "enrollments", "students"}
    assert any(column["name"] == "email" for column in table_schema["columns"])


@pytest.mark.parametrize(
    ("callable_name", "args"),
    [
        ("search", {"table": "missing_table"}),
        ("search", {"table": "students", "filters": {"missing": "x"}}),
        ("search", {"table": "students", "filters": {"score": {"op": "between", "value": [1, 2]}}}),
        ("insert", {"table": "students", "values": {}}),
        ("aggregate", {"table": "students", "metric": "median", "column": "score"}),
        ("aggregate", {"table": "students", "metric": "avg"}),
    ],
)
def test_invalid_requests_are_rejected(adapter: SQLiteAdapter, callable_name: str, args: dict) -> None:
    with pytest.raises(ValidationError):
        getattr(adapter, callable_name)(**args)


@pytest.mark.asyncio()
async def test_fastmcp_tools_and_resources_are_discoverable() -> None:
    from fastmcp import Client
    from implementation.mcp_server import mcp

    create_database(ROOT / "implementation" / "lab.db")

    async with Client(mcp) as client:
        tool_names = sorted(tool.name for tool in await client.list_tools())
        assert tool_names == ["aggregate", "insert", "search"]

        resource_uris = [str(resource.uri) for resource in await client.list_resources()]
        assert "schema://database" in resource_uris

        templates = [str(template.uriTemplate) for template in await client.list_resource_templates()]
        assert "schema://table/{table_name}" in templates

        result = await client.call_tool("aggregate", {"table": "students", "metric": "count"})
        assert result is not None


def test_schema_resource_json_is_valid(adapter: SQLiteAdapter) -> None:
    assert json.loads(json.dumps(adapter.get_database_schema()))["tables"]["students"]
