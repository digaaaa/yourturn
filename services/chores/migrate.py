
"""Apply versioned SQL Server migrations safely."""

from pathlib import Path
from time import sleep

from pymssql import OperationalError

from .database import connect


def connect_at_startup():
    for delay in (1, 2, 4, 5, 5, 5, 5, 5):
        try:
            return connect()
        except OperationalError:
            print(f"Database connection unavailable; retrying in {delay}s", flush=True)
            sleep(delay)
    return connect()


def run_migrations():
    migrations_dir = Path(__file__).parent / "migrations"

    conn = connect_at_startup()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            IF OBJECT_ID('dbo.schema_migrations', 'U') IS NULL
            CREATE TABLE dbo.schema_migrations (
                filename NVARCHAR(255) PRIMARY KEY,
                applied_at DATETIME2 NOT NULL
                    DEFAULT SYSUTCDATETIME()
            )
        """)
        conn.commit()

        for migration in sorted(migrations_dir.glob("*.sql")):
            cursor.execute(
                "SELECT COUNT(*) FROM dbo.schema_migrations "
                "WHERE filename = %s",
                (migration.name,),
            )
            if cursor.fetchone()[0]:
                continue

            sql = migration.read_text(encoding="utf-8")
            try:
                cursor.execute(sql)
                cursor.execute(
                    "INSERT INTO dbo.schema_migrations (filename) "
                    "VALUES (%s)",
                    (migration.name,),
                )
                conn.commit()
                print(f"Applied migration: {migration.name}", flush=True)
            except Exception:
                conn.rollback()
                raise
    finally:
        conn.close()


if __name__ == "__main__":
    run_migrations()
