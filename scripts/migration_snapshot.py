"""Capture Chores schema and row evidence before and after a deployment."""

import hashlib
import json
from contextlib import closing

from import_legacy import connect_target


def snapshot():
    with closing(connect_target()) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'chore_log' ORDER BY ORDINAL_POSITION"
        )
        columns = dict(cursor.fetchall())
        cursor.execute("SELECT id, chore_id, roommate_id, done_on FROM dbo.chore_log ORDER BY id")
        rows = cursor.fetchall()
        cursor.execute("SELECT filename FROM dbo.schema_migrations ORDER BY filename")
        migrations = [name for (name,) in cursor.fetchall()]
    return {
        "columns": columns,
        "row_count": len(rows),
        "first_row_id": rows[0][0] if rows else None,
        "retained_fields_sha256": hashlib.sha256(repr(rows).encode()).hexdigest(),
        "migrations": migrations,
    }


if __name__ == "__main__":
    print(json.dumps(snapshot(), sort_keys=True))
