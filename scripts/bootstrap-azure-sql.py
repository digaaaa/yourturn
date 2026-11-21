"""Grant each Azure SQL contained user access to its own database."""

import os
import re
from contextlib import closing

import pymssql


def main():
    prefix = os.environ["AZURE_PREFIX"]
    if not re.fullmatch(r"[a-z][a-z0-9-]*[a-z0-9]", prefix):
        raise ValueError("Invalid Azure resource prefix")
    config = {
        "server": f"{prefix}-sql.database.windows.net",
        "user": os.environ["SQL_ADMIN_USER"],
        "password": os.environ["SQL_ADMIN_PASSWORD"],
        "tds_version": "7.4",
        "encryption": "require",
        "login_timeout": 30,
        "autocommit": True,
    }
    passwords = {name: os.environ[f"{name.upper()}_DB_PASSWORD"] for name in ("chores", "supplies")}
    if not all(re.fullmatch(r"[A-Za-z0-9_]{16,64}", value) for value in passwords.values()):
        raise ValueError("Use 16 to 64 URL-safe letters, digits or underscores for each service password")
    if len(set(passwords.values())) != 2:
        raise ValueError("Use a different password for each database")
    for name, password in passwords.items():
        database = f"{prefix}-{name}-db"
        login = f"yourturn_{name}_app"
        try:
            with closing(pymssql.connect(database=database, **config)) as conn:
                cursor = conn.cursor()
                cursor.execute(f"IF USER_ID(N'{login}') IS NULL CREATE USER [{login}] WITH PASSWORD = %s",
                               (password,))
                cursor.execute(f"GRANT CREATE TABLE TO [{login}]")
                cursor.execute(
                    f"GRANT ALTER, REFERENCES, SELECT, INSERT, UPDATE, DELETE ON SCHEMA::dbo TO [{login}]"
                )
        except pymssql.Error as error:
            code = error.args[0] if error.args and isinstance(error.args[0], int) else "unknown"
            raise SystemExit(f"Azure SQL setup failed for {database}; database error code {code}.") from None
        print(f"Configured the contained user for {database}.")


if __name__ == "__main__":
    main()
