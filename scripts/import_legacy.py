"""Import Assignment 1 history from a read-only SQLite database, one domain at a time."""

import argparse
import json
import os
import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urlsplit
from urllib.request import urlopen

import pymssql


def connect_target():
    url = urlsplit(os.environ["DATABASE_URL"])
    if url.scheme != "mssql" or not url.hostname or not url.path.strip("/"):
        raise ValueError("Use the target service's mssql:// DATABASE_URL")
    return pymssql.connect(
        server=url.hostname, port=url.port or 1433, database=url.path.strip("/"),
        user=unquote(url.username or ""), password=unquote(url.password or ""),
        encryption="require", tds_version="7.4", login_timeout=30, timeout=30,
    )


def match_or_create(source, target, table, columns):
    fields = ", ".join(columns)
    sqlite_fields = fields.replace("[rule]", "rule")
    source_rows = source.execute(f"SELECT id, {sqlite_fields} FROM {table} ORDER BY id")
    where = " AND ".join(f"{column} = %s" for column in columns)
    markers = ", ".join(["%s"] * len(columns))
    ids = {}
    for old_id, *values in source_rows:
        target.execute(f"SELECT id FROM dbo.{table} WITH (UPDLOCK, HOLDLOCK) WHERE {where}", tuple(values))
        matches = target.fetchall()
        if len(matches) > 1:
            raise ValueError(f"Ambiguous match for source {table} ID {old_id}")
        if matches:
            ids[old_id] = matches[0][0]
        else:
            target.execute(
                f"INSERT INTO dbo.{table} ({fields}) OUTPUT INSERTED.id VALUES ({markers})", tuple(values),
            )
            ids[old_id] = target.fetchone()[0]
    return ids


def copy_history(target, table, columns, rows):
    fields = ", ".join(columns)
    markers = ", ".join(["%s"] * (len(columns) + 1))
    inserted = 0
    target.execute(f"SET IDENTITY_INSERT dbo.{table} ON")
    for old_id, *values in rows:
        target.execute(f"SELECT {fields} FROM dbo.{table} WITH (UPDLOCK, HOLDLOCK) WHERE id = %s", (old_id,))
        existing = target.fetchone()
        if existing is not None:
            if tuple(existing) != tuple(values):
                raise ValueError(f"Conflicting {table} ID {old_id}. Import to a clean target or reconcile the records.")
            continue
        target.execute(f"INSERT INTO dbo.{table} (id, {fields}) VALUES ({markers})", (old_id, *values))
        inserted += 1
    target.execute(f"SET IDENTITY_INSERT dbo.{table} OFF")
    return inserted


def import_chores(source, target):
    roommates = match_or_create(source, target, "roommates", ("name",))
    chores = match_or_create(source, target, "chores", ("name", "frequency_days", "[rule]"))
    logs = source.execute("SELECT id, chore_id, roommate_id, done_on FROM chore_log ORDER BY id")
    rows = ((key, chores[chore], roommates[person], date.fromisoformat(done)) for key, chore, person, done in logs)
    return copy_history(target, "chore_log", ("chore_id", "roommate_id", "done_on"), rows)


def import_supplies(source, target):
    base = os.environ["CHORES_SERVICE_URL"].rstrip("/")
    with urlopen(base + "/roommates", timeout=15) as response:
        roster = {person["name"]: person["id"] for person in json.load(response)}
    people = {key: roster[name] for key, name in source.execute("SELECT id, name FROM roommates")}
    supplies = match_or_create(source, target, "supplies", ("name", "[rule]"))
    purchases = source.execute("SELECT id, supply_id, roommate_id, price, bought_on FROM purchases ORDER BY id")
    rows = ((key, supplies[supply], people[person], price, date.fromisoformat(bought))
            for key, supply, person, price, bought in purchases)
    return copy_history(target, "purchases", ("supply_id", "roommate_id", "price", "bought_on"), rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("domain", choices=["chores", "supplies"])
    parser.add_argument("sqlite", type=Path)
    options = parser.parse_args()
    uri = options.sqlite.resolve(strict=True).as_uri() + "?mode=ro"
    transfer = import_chores if options.domain == "chores" else import_supplies
    with closing(sqlite3.connect(uri, uri=True)) as source, closing(connect_target()) as destination:
        source.execute("BEGIN")
        try:
            count = transfer(source, destination.cursor())
            destination.commit()
        except BaseException:
            destination.rollback()
            raise
    print(f"{options.domain}: imported {count} new records.")


if __name__ == "__main__":
    main()
