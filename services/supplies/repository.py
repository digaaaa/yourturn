"""All SQL for the supplies domain. No decisions here, only reading and writing."""


class SupplyRepository:
    def __init__(self, conn, roommates):
        self.conn = conn
        self.roommates = roommates

    def _query(self, sql, params=()):
        cursor = self.conn.cursor(as_dict=True)
        cursor.execute(sql, params)
        return cursor

    def list_supplies(self):
        return self._query("SELECT id, name, [rule] FROM supplies ORDER BY id").fetchall()

    def get_supply(self, supply_id):
        return self._query(
            "SELECT id, name, [rule] FROM supplies WHERE id = %s", (supply_id,)
        ).fetchone()

    def list_roommates(self):
        return self.roommates

    def purchases(self, supply_id):
        """Who bought this supply, for how much and when, oldest first."""
        return self._query(
            "SELECT roommate_id, price, CONVERT(char(10), bought_on, 23) AS bought_on FROM purchases "
            "WHERE supply_id = %s ORDER BY bought_on, id",
            (supply_id,),
        ).fetchall()

    def spent_since(self, start_date):
        """How much each roommate spent on all supplies from start_date onwards."""
        return self._query(
            "SELECT roommate_id, SUM(price) AS spent FROM purchases "
            "WHERE bought_on >= %s GROUP BY roommate_id",
            (start_date,),
        ).fetchall()

    def add_purchase(self, supply_id, roommate_id, price, bought_on):
        self._query(
            "INSERT INTO purchases (supply_id, roommate_id, price, bought_on) VALUES (%s, %s, %s, %s)",
            (supply_id, roommate_id, price, bought_on),
        )
        self.conn.commit()
