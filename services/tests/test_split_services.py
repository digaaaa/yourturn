"""Tests for the split Flask APIs, domain logic and HTTP boundary."""

import unittest
from contextlib import contextmanager
from datetime import date
from threading import Thread
from unittest.mock import MagicMock, Mock, patch

import pymssql
from werkzeug.serving import make_server

from services.chores import app as chores_api
from services.chores.repository import ChoreRepository
from services.chores.service import ChoreService
from services.supplies import app as supplies_api
from services.supplies.repository import SupplyRepository
from services.supplies.service import SupplyService


TODAY = date(2026, 11, 20)
ROOMMATES = [{"id": 1, "name": "Alex"}, {"id": 2, "name": "Sam"}]
CHORE = {"id": 1, "name": "Dishes", "frequency_days": 1, "rule": "take_turns"}
SUPPLY = {"id": 1, "name": "Eggs", "rule": "least_spent"}


@contextmanager
def serve(app):
    server = make_server("127.0.0.1", 0, app)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        worker.join()
        server.server_close()


class ChoresTests(unittest.TestCase):
    def setUp(self):
        self.repo = Mock(spec=ChoreRepository)
        self.repo.list_roommates.return_value = ROOMMATES
        self.repo.list_chores.return_value = [CHORE]
        self.repo.get_chore.return_value = CHORE
        self.repo.history.return_value = [{"roommate_id": 1, "done_on": "2026-11-16"}]
        self.service = ChoreService(self.repo)

    def test_overdue_chore_advances_the_turn(self):
        entry, = self.service.overview(TODAY)
        self.assertEqual(entry["next_person"], "Sam")
        self.assertEqual(entry["days_overdue"], 3)

    def test_monthly_stats_include_roommates_with_no_completions(self):
        self.repo.count_done_since.return_value = [{"roommate_id": 2, "done": 3}]
        self.assertEqual(self.service.monthly_stats(TODAY), [
            {"name": "Sam", "done": 3}, {"name": "Alex", "done": 0},
        ])
        self.repo.count_done_since.assert_called_once_with("2026-11-01")

    def test_completion_api_records_the_selected_roommate(self):
        with patch.object(chores_api, "connect", return_value=MagicMock()), \
                patch.object(chores_api, "ChoreRepository", return_value=self.repo), \
                patch.object(chores_api, "date") as calendar:
            calendar.today.return_value = TODAY
            response = chores_api.app.test_client().post("/chores/1/done", json={"roommate_id": 2})
        self.assertEqual(response.status_code, 204)
        self.repo.add_log.assert_called_once_with(1, 2, "2026-11-20")

    def test_unknown_roommate_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown roommate"):
            self.service.mark_done(1, 3, TODAY)
        self.repo.add_log.assert_not_called()


class SuppliesTests(unittest.TestCase):
    def setUp(self):
        self.repo = Mock(spec=SupplyRepository)
        self.repo.list_roommates.return_value = ROOMMATES
        self.repo.list_supplies.return_value = [SUPPLY]
        self.repo.get_supply.return_value = SUPPLY
        self.repo.purchases.return_value = [
            {"roommate_id": 1, "price": 7, "bought_on": "2026-11-10"},
            {"roommate_id": 2, "price": 3, "bought_on": "2026-11-19"},
        ]
        self.service = SupplyService(self.repo)

    def test_least_spent_rule_uses_purchase_history(self):
        entry, = self.service.overview()
        self.assertEqual(entry["next_person"], "Sam")
        self.assertEqual(entry["last_price"], 3)

    def test_monthly_spending_includes_roommates_who_spent_nothing(self):
        self.repo.spent_since.return_value = [{"roommate_id": 2, "spent": 8.236}]
        self.assertEqual(self.service.monthly_spending(TODAY), [
            {"name": "Sam", "spent": 8.24}, {"name": "Alex", "spent": 0},
        ])
        self.repo.spent_since.assert_called_once_with("2026-11-01")

    def test_purchase_api_records_rounded_price(self):
        with patch.object(supplies_api, "get_roommates", return_value=ROOMMATES), \
                patch.object(supplies_api, "connect", return_value=MagicMock()), \
                patch.object(supplies_api, "SupplyRepository", return_value=self.repo), \
                patch.object(supplies_api, "date") as calendar:
            calendar.today.return_value = TODAY
            response = supplies_api.app.test_client().post(
                "/supplies/1/bought", json={"roommate_id": 2, "price": 4.237}
            )
        self.assertEqual(response.status_code, 204)
        self.repo.add_purchase.assert_called_once_with(1, 2, 4.24, "2026-11-20")

    def test_invalid_prices_are_rejected(self):
        for price in (-1, 0, 1001, float("nan"), float("inf")):
            with self.subTest(price=price), self.assertRaisesRegex(ValueError, "Price"):
                self.service.record_purchase(1, 1, price, TODAY)
        self.repo.add_purchase.assert_not_called()


class ServiceBoundaryTests(unittest.TestCase):
    def test_supplies_uses_roommates_returned_over_http_by_chores(self):
        chores = Mock(spec=ChoreRepository)
        chores.list_roommates.return_value = [{"id": 42, "name": "From Chores"}]
        with patch.object(chores_api, "connect", return_value=MagicMock()), \
                patch.object(chores_api, "ChoreRepository", return_value=chores), \
                serve(chores_api.app) as chores_url, \
                patch.dict("os.environ", {"CHORES_SERVICE_URL": chores_url}), \
                patch.object(supplies_api, "connect", return_value=MagicMock()), \
                patch.object(SupplyRepository, "list_supplies", return_value=[SUPPLY]), \
                patch.object(SupplyRepository, "get_supply", return_value=SUPPLY), \
                patch.object(SupplyRepository, "purchases", return_value=[]), \
                patch.object(SupplyRepository, "spent_since", return_value=[]):
            response = supplies_api.app.test_client().get("/supplies/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["roommates"], [{"id": 42, "name": "From Chores"}])
        self.assertEqual(response.json["supplies"][0]["next_person"], "From Chores")
        chores.list_roommates.assert_called_once()

    def test_chores_reads_supply_spending_over_http(self):
        chores = Mock(spec=ChoreRepository)
        chores.list_roommates.return_value = ROOMMATES
        supplies = Mock(spec=SupplyRepository)
        supplies.spent_since.return_value = [{"roommate_id": 2, "spent": 4.25}]
        with patch.object(supplies_api, "connect", return_value=MagicMock()), \
                patch.object(supplies_api, "SupplyRepository", return_value=supplies), \
                serve(supplies_api.app) as supplies_url, \
                patch.dict("os.environ", {"SUPPLIES_SERVICE_URL": supplies_url}), \
                patch.object(chores_api, "connect", return_value=MagicMock()), \
                patch.object(chores_api, "ChoreRepository", return_value=chores):
            response = chores_api.app.test_client().get("/chores/household-summary")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["spending"], [
            {"name": "Alex", "spent": 0}, {"name": "Sam", "spent": 4.25},
        ])

    def test_supplies_times_out_and_keeps_inventory_available(self):
        repo = Mock(spec=SupplyRepository)
        repo.list_roommates.return_value = []
        repo.list_supplies.return_value = [SUPPLY]
        repo.purchases.return_value = []
        repo.spent_since.return_value = []
        with patch.dict("os.environ", {"CHORES_SERVICE_URL": "http://example.invalid"}), \
                patch.object(supplies_api, "urlopen", side_effect=TimeoutError) as fetch, \
                patch.object(supplies_api, "connect", return_value=MagicMock()), \
                patch.object(supplies_api, "SupplyRepository", return_value=repo):
            client = supplies_api.app.test_client()
            inventory = client.get("/supplies/")
            purchase = client.post("/supplies/1/bought", json={"roommate_id": 1, "price": 4.25})
        self.assertEqual(inventory.status_code, 200)
        self.assertEqual(inventory.json["supplies"][0]["name"], "Eggs")
        self.assertIsNone(inventory.json["supplies"][0]["next_person"])
        self.assertIn("unavailable", inventory.json["warning"])
        self.assertEqual(purchase.status_code, 503)
        self.assertEqual(fetch.call_count, 2)
        self.assertTrue(all(call.kwargs["timeout"] == 2 for call in fetch.call_args_list))
        repo.add_purchase.assert_not_called()

    def test_health_returns_503_if_own_database_is_down(self):
        for module in (chores_api, supplies_api):
            with self.subTest(service=module.__name__), \
                    patch.object(module, "connect", side_effect=pymssql.OperationalError):
                response = module.app.test_client().get("/health")
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json["db"], "unavailable")
