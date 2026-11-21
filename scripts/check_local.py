"""Smoke check for a fresh Compose stack. It creates two test records."""

import json
import os
import time
from urllib.error import URLError
from urllib.request import Request, urlopen


def call(base, path, payload=None):
    options = {}
    if payload is not None:
        options = {
            "data": json.dumps(payload).encode(),
            "headers": {"Content-Type": "application/json"},
        }
    with urlopen(Request(base + path, **options), timeout=5) as response:
        if response.status == 204:
            return None
        return json.load(response)


def wait_for_health(base):
    for _ in range(60):
        try:
            health = call(base, "/health")
            if health["db"] == "ok":
                assert health["version"] == os.environ.get("APP_VERSION", "local"), health
                return
        except (URLError, OSError):
            pass
        time.sleep(2)
    raise RuntimeError(f"Service stayed unhealthy at {base}")


def main():
    chores = "http://localhost:" + os.environ.get("CHORES_PORT", "8001")
    supplies = "http://localhost:" + os.environ.get("SUPPLIES_PORT", "8002")
    wait_for_health(chores)
    wait_for_health(supplies)
    roster = call(chores, "/roommates")
    chores_before = call(chores, "/chores/")
    supplies_before = call(supplies, "/supplies/")
    assert roster and supplies_before["roommates"] == roster
    roommate = roster[0]
    chore = chores_before["chores"][0]
    supply = supplies_before["supplies"][0]
    previous_done = next(row["done"] for row in chores_before["stats"] if row["name"] == roommate["name"])
    assert call(chores, f"/chores/{chore['id']}/done", {"roommate_id": roommate["id"]}) is None
    assert call(supplies, f"/supplies/{supply['id']}/bought", {
        "roommate_id": roommate["id"], "price": 4.25,
    }) is None
    chores_after = call(chores, "/chores/")
    supplies_after = call(supplies, "/supplies/")
    assert next(row["done"] for row in chores_after["stats"] if row["name"] == roommate["name"]) == previous_done + 1
    assert supplies_after["supplies"][0]["last_price"] == 4.25
    summary = call(chores, "/chores/household-summary")
    spent = next(row["spent"] for row in summary["spending"] if row["name"] == roommate["name"])
    previous_spent = next(row["spent"] for row in supplies_before["spending"] if row["name"] == roommate["name"])
    assert spent == round(previous_spent + 4.25, 2)
    print("Both SQL-backed APIs persisted writes and returned cross-service data.")


if __name__ == "__main__":
    main()
