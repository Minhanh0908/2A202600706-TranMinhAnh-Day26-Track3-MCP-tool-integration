from __future__ import annotations

import os
import sqlite3
from pathlib import Path

try:
    from .db import DEFAULT_DB_PATH
except ImportError:
    from db import DEFAULT_DB_PATH


SCHEMA_SQL = """
DROP TABLE IF EXISTS enrollments;
DROP TABLE IF EXISTS courses;
DROP TABLE IF EXISTS students;

CREATE TABLE students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    cohort TEXT NOT NULL,
    score REAL NOT NULL CHECK (score >= 0 AND score <= 100),
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    credits INTEGER NOT NULL CHECK (credits > 0)
);

CREATE TABLE enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('enrolled', 'completed', 'dropped')),
    grade REAL CHECK (grade IS NULL OR (grade >= 0 AND grade <= 100)),
    FOREIGN KEY (student_id) REFERENCES students(id),
    FOREIGN KEY (course_id) REFERENCES courses(id)
);
"""


SEED_SQL = """
INSERT INTO students (name, email, cohort, score, active) VALUES
    ('An Nguyen', 'an.nguyen@example.edu', 'A1', 88.5, 1),
    ('Binh Tran', 'binh.tran@example.edu', 'A1', 92.0, 1),
    ('Chi Le', 'chi.le@example.edu', 'B1', 76.0, 1),
    ('Dung Pham', 'dung.pham@example.edu', 'B1', 81.5, 0),
    ('Ha Vo', 'ha.vo@example.edu', 'A2', 95.0, 1);

INSERT INTO courses (code, title, credits) VALUES
    ('MCP101', 'Model Context Protocol Basics', 3),
    ('DB201', 'Practical SQLite', 4),
    ('AI301', 'Applied AI Tooling', 3);

INSERT INTO enrollments (student_id, course_id, status, grade) VALUES
    (1, 1, 'completed', 89.0),
    (1, 2, 'enrolled', NULL),
    (2, 1, 'completed', 94.0),
    (2, 3, 'enrolled', NULL),
    (3, 2, 'completed', 78.0),
    (4, 1, 'dropped', 55.0),
    (5, 3, 'completed', 97.0);
"""


def get_database_path() -> Path:
    return Path(os.environ.get("SQLITE_LAB_DB", DEFAULT_DB_PATH))


def create_database(db_path: str | Path | None = None) -> Path:
    path = Path(db_path) if db_path is not None else get_database_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA_SQL)
        conn.executescript(SEED_SQL)
        conn.commit()

    return path


if __name__ == "__main__":
    created_path = create_database()
    print(f"Created SQLite lab database at {created_path}")
