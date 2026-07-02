from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from fastmcp import Client

try:
    from .init_db import create_database
    from .mcp_server import mcp
except ImportError:
    from init_db import create_database
    from mcp_server import mcp


def content_to_python(result: Any) -> Any:
    if hasattr(result, "data") and result.data is not None:
        return result.data

    content = getattr(result, "content", result)
    if isinstance(content, list) and content:
        first = content[0]
        text = getattr(first, "text", None)
        if text is not None:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
    return result


async def main() -> None:
    logging.getLogger("fastmcp").setLevel(logging.CRITICAL)
    create_database()

    async with Client(mcp) as client:
        tools = await client.list_tools()
        tool_names = sorted(tool.name for tool in tools)
        print(f"Tools: {tool_names}")
        assert tool_names == ["aggregate", "insert", "search"]

        resources = await client.list_resources()
        resource_uris = sorted(str(resource.uri) for resource in resources)
        print(f"Resources: {resource_uris}")
        assert "schema://database" in resource_uris

        templates = await client.list_resource_templates()
        template_uris = sorted(str(template.uriTemplate) for template in templates)
        print(f"Resource templates: {template_uris}")
        assert "schema://table/{table_name}" in template_uris

        search_result = content_to_python(
            await client.call_tool(
                "search",
                {
                    "table": "students",
                    "filters": {"cohort": "A1"},
                    "columns": ["id", "name", "cohort", "score"],
                    "order_by": "score",
                    "descending": True,
                    "limit": 5,
                },
            )
        )
        print(f"Search rows: {search_result['rows']}")
        assert search_result["count"] == 2

        insert_result = content_to_python(
            await client.call_tool(
                "insert",
                {
                    "table": "students",
                    "values": {
                        "name": "Minh Anh",
                        "email": "minh.anh@example.edu",
                        "cohort": "A2",
                        "score": 86.0,
                    },
                },
            )
        )
        print(f"Inserted: {insert_result['row']}")
        assert insert_result["row"]["email"] == "minh.anh@example.edu"

        aggregate_result = content_to_python(
            await client.call_tool(
                "aggregate",
                {"table": "students", "metric": "avg", "column": "score", "group_by": "cohort"},
            )
        )
        print(f"Aggregate rows: {aggregate_result['rows']}")
        assert aggregate_result["rows"]

        database_schema = await client.read_resource("schema://database")
        print(f"Database schema content blocks: {len(database_schema)}")

        table_schema = await client.read_resource("schema://table/students")
        print(f"Students schema content blocks: {len(table_schema)}")

        invalid_result = await client.call_tool(
            "search",
            {"table": "missing_table"},
            raise_on_error=False,
        )
        assert invalid_result.is_error
        print(f"Invalid call failed as expected: {invalid_result.content[0].text}")

    print("Verification completed successfully.")


if __name__ == "__main__":
    asyncio.run(main())
