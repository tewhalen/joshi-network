import sqlite3


class DBWrapper:
    sqldb: sqlite3.Connection

    def _select_and_fetchone(self, query: str, params: tuple) -> tuple | None:
        """Helper method to execute a select query and fetch one result."""
        cursor = self.sqldb.cursor()
        cursor.execute(query, params)
        row = cursor.fetchone()
        cursor.close()
        return row

    def _select_and_fetchone_dict(self, query: str, params: tuple) -> dict | None:
        """Helper method to execute a select query and fetch one result as a dict."""
        cursor = self.sqldb.cursor()
        cursor.execute(query, params)
        row = cursor.fetchone()
        if row:
            col_names = [description[0] for description in cursor.description]
            d = dict(zip(col_names, row))
            cursor.close()
            return d
        else:
            cursor.close()
            return None

    def _select_and_fetchall(self, query: str, params: tuple) -> list[tuple]:
        """Helper method to execute a select query and fetch all results."""
        cursor = self.sqldb.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        return rows

    def _execute_and_commit(self, query: str, params: tuple) -> int:
        """Helper method to execute a query and commit changes."""
        cursor = self.sqldb.cursor()
        cursor.execute(query, params)
        self.sqldb.commit()
        rowcount = cursor.rowcount
        cursor.close()

        # return the status of the execution if needed
        return rowcount
