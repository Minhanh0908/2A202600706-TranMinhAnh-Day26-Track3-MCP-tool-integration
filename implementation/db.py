from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


DEFAULT_DB_PATH = Path(__file__).with_name("lab.db")


class ValidationError(ValueError):
    """Raised when a request cannot be safely executed."""


class SQLiteAdapter:
    """Small validated SQLite data-access layer for the MCP tools."""

    SUPPORTED_OPERATORS = {"eq", "ne", "lt", "lte", "gt", "gte", "like", "in"}
    AGGREGATE_METRICS = {"count", "avg", "sum", "min", "max"}
    MAX_LIMIT = 100

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def list_tables(self) -> list[str]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            ).fetchall()
        return [row["name"] for row in rows]

    def get_table_schema(self, table: str) -> dict[str, Any]:
        self.validate_table(table)
        with self.connect() as conn:
            rows = conn.execute(f"PRAGMA table_info({self.quote_identifier(table)})").fetchall()

        columns = [
            {
                "name": row["name"],
                "type": row["type"],
                "not_null": bool(row["notnull"]),
                "default": row["dflt_value"],
                "primary_key": bool(row["pk"]),
            }
            for row in rows
        ]
        return {"table": table, "columns": columns}

    def get_database_schema(self) -> dict[str, Any]:
        return {"tables": {table: self.get_table_schema(table) for table in self.list_tables()}}

    def search(
        self,
        table: str,
        columns: list[str] | None = None,
        filters: dict[str, Any] | list[dict[str, Any]] | None = None,
        limit: int = 20,
        offset: int = 0,
        order_by: str | None = None,
        descending: bool = False,
    ) -> dict[str, Any]:
        table_columns = self.validate_table(table)
        selected_columns = self.validate_selected_columns(columns, table_columns)
        safe_limit = self.validate_limit(limit)
        safe_offset = self.validate_offset(offset)
        where_sql, params = self.build_where_clause(table_columns, filters)

        select_sql = ", ".join(self.quote_identifier(column) for column in selected_columns)
        sql = f"SELECT {select_sql} FROM {self.quote_identifier(table)}{where_sql}"

        if order_by is not None:
            self.validate_column(order_by, table_columns)
            direction = "DESC" if descending else "ASC"
            sql += f" ORDER BY {self.quote_identifier(order_by)} {direction}"

        sql += " LIMIT ? OFFSET ?"
        params.extend([safe_limit, safe_offset])

        with self.connect() as conn:
            rows = [dict(row) for row in conn.execute(sql, params).fetchall()]

        return {
            "table": table,
            "columns": selected_columns,
            "rows": rows,
            "count": len(rows),
            "limit": safe_limit,
            "offset": safe_offset,
        }

    def insert(self, table: str, values: dict[str, Any]) -> dict[str, Any]:
        table_columns = self.validate_table(table)
        if not isinstance(values, dict) or not values:
            raise ValidationError("insert values must be a non-empty object")

        for column in values:
            self.validate_column(column, table_columns)

        columns = list(values.keys())
        placeholders = ", ".join("?" for _ in columns)
        column_sql = ", ".join(self.quote_identifier(column) for column in columns)
        sql = f"INSERT INTO {self.quote_identifier(table)} ({column_sql}) VALUES ({placeholders})"

        try:
            with self.connect() as conn:
                cursor = conn.execute(sql, [values[column] for column in columns])
                inserted_id = cursor.lastrowid
                conn.commit()
                row = conn.execute(
                    f"SELECT * FROM {self.quote_identifier(table)} WHERE rowid = ?",
                    [inserted_id],
                ).fetchone()
        except sqlite3.IntegrityError as exc:
            raise ValidationError(f"insert failed integrity check: {exc}") from exc

        return {
            "table": table,
            "inserted_id": inserted_id,
            "row": dict(row) if row is not None else dict(values),
        }

    def aggregate(
        self,
        table: str,
        metric: str,
        column: str | None = None,
        filters: dict[str, Any] | list[dict[str, Any]] | None = None,
        group_by: str | None = None,
    ) -> dict[str, Any]:
        table_columns = self.validate_table(table)
        metric = self.validate_metric(metric)

        if metric == "count" and column is None:
            aggregate_expr = "COUNT(*)"
        else:
            if column is None:
                raise ValidationError(f"metric '{metric}' requires a column")
            self.validate_column(column, table_columns)
            aggregate_expr = f"{metric.upper()}({self.quote_identifier(column)})"

        select_parts = []
        if group_by is not None:
            self.validate_column(group_by, table_columns)
            select_parts.append(self.quote_identifier(group_by))
        select_parts.append(f"{aggregate_expr} AS value")

        where_sql, params = self.build_where_clause(table_columns, filters)
        sql = f"SELECT {', '.join(select_parts)} FROM {self.quote_identifier(table)}{where_sql}"

        if group_by is not None:
            sql += f" GROUP BY {self.quote_identifier(group_by)} ORDER BY {self.quote_identifier(group_by)}"

        with self.connect() as conn:
            rows = [dict(row) for row in conn.execute(sql, params).fetchall()]

        return {
            "table": table,
            "metric": metric,
            "column": column,
            "group_by": group_by,
            "rows": rows,
        }

    def validate_table(self, table: str) -> set[str]:
        if not isinstance(table, str) or not table:
            raise ValidationError("table must be a non-empty string")
        if table not in self.list_tables():
            raise ValidationError(f"unknown table: {table}")
        return self.get_column_names(table)

    def get_column_names(self, table: str) -> set[str]:
        with self.connect() as conn:
            rows = conn.execute(f"PRAGMA table_info({self.quote_identifier(table)})").fetchall()
        return {row["name"] for row in rows}

    def validate_selected_columns(self, columns: list[str] | None, table_columns: set[str]) -> list[str]:
        if columns is None:
            return sorted(table_columns)
        if not isinstance(columns, list) or not columns:
            raise ValidationError("columns must be a non-empty list when provided")
        for column in columns:
            self.validate_column(column, table_columns)
        return columns

    def validate_column(self, column: str, table_columns: set[str]) -> None:
        if not isinstance(column, str) or not column:
            raise ValidationError("column names must be non-empty strings")
        if column not in table_columns:
            raise ValidationError(f"unknown column: {column}")

    def validate_metric(self, metric: str) -> str:
        if not isinstance(metric, str):
            raise ValidationError("metric must be a string")
        normalized = metric.lower()
        if normalized not in self.AGGREGATE_METRICS:
            supported = ", ".join(sorted(self.AGGREGATE_METRICS))
            raise ValidationError(f"unsupported metric: {metric}; supported metrics: {supported}")
        return normalized

    def validate_limit(self, limit: int) -> int:
        if not isinstance(limit, int) or isinstance(limit, bool):
            raise ValidationError("limit must be an integer")
        if limit < 1 or limit > self.MAX_LIMIT:
            raise ValidationError(f"limit must be between 1 and {self.MAX_LIMIT}")
        return limit

    def validate_offset(self, offset: int) -> int:
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise ValidationError("offset must be a non-negative integer")
        return offset

    def build_where_clause(
        self,
        table_columns: set[str],
        filters: dict[str, Any] | list[dict[str, Any]] | None,
    ) -> tuple[str, list[Any]]:
        normalized_filters = self.normalize_filters(filters)
        if not normalized_filters:
            return "", []

        clauses: list[str] = []
        params: list[Any] = []
        sql_ops = {
            "eq": "=",
            "ne": "!=",
            "lt": "<",
            "lte": "<=",
            "gt": ">",
            "gte": ">=",
            "like": "LIKE",
        }

        for item in normalized_filters:
            column = item["column"]
            operator = item["op"]
            value = item["value"]
            self.validate_column(column, table_columns)

            if operator not in self.SUPPORTED_OPERATORS:
                supported = ", ".join(sorted(self.SUPPORTED_OPERATORS))
                raise ValidationError(f"unsupported filter operator: {operator}; supported operators: {supported}")

            quoted_column = self.quote_identifier(column)
            if operator == "in":
                if not isinstance(value, list) or not value:
                    raise ValidationError("operator 'in' requires a non-empty list value")
                placeholders = ", ".join("?" for _ in value)
                clauses.append(f"{quoted_column} IN ({placeholders})")
                params.extend(value)
            elif operator == "eq" and value is None:
                clauses.append(f"{quoted_column} IS NULL")
            elif operator == "ne" and value is None:
                clauses.append(f"{quoted_column} IS NOT NULL")
            else:
                clauses.append(f"{quoted_column} {sql_ops[operator]} ?")
                params.append(value)

        return " WHERE " + " AND ".join(clauses), params

    def normalize_filters(self, filters: dict[str, Any] | list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        if filters is None:
            return []

        if isinstance(filters, dict):
            normalized = []
            for column, condition in filters.items():
                if isinstance(condition, dict):
                    normalized.append(
                        {
                            "column": column,
                            "op": condition.get("op", "eq"),
                            "value": condition.get("value"),
                        }
                    )
                else:
                    normalized.append({"column": column, "op": "eq", "value": condition})
            return normalized

        if isinstance(filters, list):
            normalized = []
            for condition in filters:
                if not isinstance(condition, dict):
                    raise ValidationError("each filter must be an object")
                if "column" not in condition or "value" not in condition:
                    raise ValidationError("list filters require column and value fields")
                normalized.append(
                    {
                        "column": condition["column"],
                        "op": condition.get("op", "eq"),
                        "value": condition["value"],
                    }
                )
            return normalized

        raise ValidationError("filters must be an object, a list, or null")

    @staticmethod
    def quote_identifier(identifier: str) -> str:
        return '"' + identifier.replace('"', '""') + '"'
