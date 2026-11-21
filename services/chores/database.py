
"""SQL Server connection for the Chores service."""

import os
from urllib.parse import urlparse, unquote

import pymssql


def connect():
    """Connect to the Chores database using DATABASE_URL."""
    database_url = os.environ["DATABASE_URL"]
    parsed = urlparse(database_url)

    if parsed.scheme != "mssql":
        raise ValueError("DATABASE_URL must start with mssql://")

    return pymssql.connect(
        server=parsed.hostname,
        port=parsed.port or 1433,
        user=unquote(parsed.username or ""),
        password=unquote(parsed.password or ""),
        database=parsed.path.lstrip("/"),
        login_timeout=10,
        timeout=10,
        encryption="require",
        tds_version="7.4",
    )
