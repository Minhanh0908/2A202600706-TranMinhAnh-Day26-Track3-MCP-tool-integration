# Lab: Build a Database MCP Server with FastMCP and SQLite

This repository contains a working FastMCP server backed by SQLite. It exposes:

- `search`
- `insert`
- `aggregate`
- `schema://database`
- `schema://table/{table_name}`

The implementation uses a small relational dataset with `students`, `courses`, and `enrollments`.

## Project Structure

```text
implementation/
  __init__.py
  db.py
  init_db.py
  mcp_server.py
  verify_server.py
  tests/
    test_server.py
pseudocode/
  db.py
  init_db.py
  mcp_server.py
requirements.txt
Rubric.md
Tips.md
```

## Setup

Create a virtual environment if desired, then install dependencies:

```bash
python -m pip install -r requirements.txt
```

Initialize the SQLite database:

```bash
python implementation/init_db.py
```

By default this creates:

```text
implementation/lab.db
```

You can override the database path with:

```bash
set SQLITE_LAB_DB=C:\absolute\path\to\lab.db
```

## Run the MCP Server

```bash
python implementation/mcp_server.py
```

The server uses stdio transport by default, which is the simplest setup for local MCP clients.

## Tools

### `search`

Search rows with validated columns, filters, ordering, limit, and offset.

Example payload:

```json
{
  "table": "students",
  "filters": {
    "cohort": "A1",
    "score": {
      "op": "gte",
      "value": 80
    }
  },
  "columns": ["id", "name", "cohort", "score"],
  "order_by": "score",
  "descending": true,
  "limit": 10,
  "offset": 0
}
```

Supported filter operators:

- `eq`
- `ne`
- `lt`
- `lte`
- `gt`
- `gte`
- `like`
- `in`

### `insert`

Insert one row and return the inserted row.

Example payload:

```json
{
  "table": "students",
  "values": {
    "name": "Minh Anh",
    "email": "minh.anh@example.edu",
    "cohort": "A2",
    "score": 86.0
  }
}
```

### `aggregate`

Run simple aggregate metrics with optional filters and grouping.

Example payload:

```json
{
  "table": "students",
  "metric": "avg",
  "column": "score",
  "group_by": "cohort"
}
```

Supported metrics:

- `count`
- `avg`
- `sum`
- `min`
- `max`

`count` can omit `column` and will use `COUNT(*)`. Other metrics require a valid column.

## Resources

Read the full database schema:

```text
schema://database
```

Read one table schema:

```text
schema://table/students
```

## Validation and Safety

The adapter rejects:

- unknown table names
- unknown column names
- unsupported filter operators
- invalid aggregate requests
- empty inserts
- invalid limit and offset values

SQL values are passed through bound parameters. Table and column identifiers are accepted only after schema validation.

## Verification

Run the automated test suite:

```bash
pytest implementation/tests
```

Run the end-to-end FastMCP smoke test:

```bash
python implementation/verify_server.py
```

The verification script checks:

- tool discovery
- resource discovery
- resource template discovery
- valid `search`, `insert`, and `aggregate` calls
- schema reads
- invalid request handling

## MCP Inspector

Install dependencies first, then run Inspector with your absolute Python and server paths:

```bash
npx -y @modelcontextprotocol/inspector python D:\AI20K\Lab\2A202600706-TranMinhAnh-Day26-Track3-MCP-tool-integration\implementation\mcp_server.py
```

In Inspector, verify:

- `search`, `insert`, and `aggregate` appear in tools
- `schema://database` appears in resources
- `schema://table/{table_name}` appears as a resource template
- valid calls return structured results
- invalid calls return clear errors

## Codex MCP Client Configuration

Add this to `~/.codex/config.toml`, replacing the path if this repo is elsewhere:

```toml
[mcp_servers.sqlite_lab]
command = "python"
args = ["D:\\AI20K\\Lab\\2A202600706-TranMinhAnh-Day26-Track3-MCP-tool-integration\\implementation\\mcp_server.py"]
```

Suggested prompt for a client demo:

```text
Use the sqlite_lab MCP server. Read schema://database, search the top 2 students by score, then compute average student score by cohort.
```

## Two-Minute Demo Checklist

1. Show `python implementation/init_db.py`.
2. Show `python implementation/verify_server.py`.
3. Open MCP Inspector or Codex client configuration.
4. Show the three tools are discoverable.
5. Read `schema://database`.
6. Run `search` for students in cohort `A1`.
7. Run `insert` for a new student.
8. Run `aggregate` average score by cohort.
9. Run an invalid request such as `{"table": "missing_table"}` and show the clear error.
