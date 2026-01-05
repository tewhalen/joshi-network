import pathlib
import sqlite3
from contextlib import contextmanager


class DBWrapper:
    sqldb_ro: sqlite3.Connection
    __sqldb_rw: None | sqlite3.Connection
    path: pathlib.Path

    def __init__(self, path: pathlib.Path):
        self.path = path
        # Always-open read-only connection
        self.sqldb_ro = sqlite3.connect(
            f"file:{self.path.with_suffix('.sqlite3')}?mode=ro", uri=True
        )
        self.__sqldb_rw = None  # Temporary write connection, only set in context

    @property
    def sqldb_rw(self) -> sqlite3.Connection:
        """Return the read/write connection, or raise if not in writable context."""
        if self.__sqldb_rw is None:
            raise RuntimeError("Not in writable context!")
        return self.__sqldb_rw

    @contextmanager
    def writable(self):
        """Context manager for temporarily enabling write access on this instance.

        Opens a new write connection (self.sqldb_rw) for the duration of the context.
        All write methods use this connection if present.
        """
        if self.__sqldb_rw is not None:
            raise RuntimeError("Already in writable context!")
        self.__sqldb_rw = sqlite3.connect(str(self.path.with_suffix(".sqlite3")))

        try:
            yield self
        finally:
            self.__sqldb_rw.close()
            self.__sqldb_rw = None

    def _select_and_fetchone(self, query: str, params: tuple) -> tuple | None:
        """Helper method to execute a select query and fetch one result."""
        cursor = self.sqldb_ro.cursor()
        cursor.execute(query, params)
        row = cursor.fetchone()
        cursor.close()
        return row

    def _select_and_fetchone_dict(self, query: str, params: tuple) -> dict | None:
        """Helper method to execute a select query and fetch one result as a dict."""
        cursor = self.sqldb_ro.cursor()
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
        cursor = self.sqldb_ro.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        return rows

    def _execute_and_commit(self, query: str, params: tuple) -> int:
        """Helper method to execute a query and commit changes."""
        cursor = self.sqldb_rw.cursor()
        cursor.execute(query, params)
        self.sqldb_rw.commit()
        rowcount = cursor.rowcount
        cursor.close()

        # return the status of the execution if needed
        return rowcount

    def _execute(self, query: str, params: tuple) -> int:
        """Helper method to execute a query without out committing changes."""
        cursor = self.sqldb_rw.cursor()
        cursor.execute(query, params)
        rowcount = cursor.rowcount
        cursor.close()

        # return the status of the execution if needed
        return rowcount

    def _rw_cursor(self) -> sqlite3.Cursor:
        """Create and return a read/write cursor"""
        return self.sqldb_rw.cursor()

    def _commit(self):
        """Commit on the r/w connection."""
        self.sqldb_rw.commit()
