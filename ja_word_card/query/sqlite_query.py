from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pykakasi

from .base import BaseQuery, DictWord


class SQLiteQuery(BaseQuery):
    name = "SQLite"

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self._kakasi = pykakasi.kakasi()
        self._loaded = self._check_database()

    def is_loaded(self) -> bool:
        return self._loaded

    def query(self, text: str) -> DictWord:
        if not self._loaded:
            raise RuntimeError(f"Database is not loaded: {self.database_path}")

        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            row = self._query_text(connection, text)
            if row is None:
                pronounce = self._pronounce_text(text)
                if pronounce and pronounce != text:
                    row = self._query_text(connection, pronounce)

        if row is None:
            raise KeyError(f"Word not found: {text}")

        return self._row_to_word(row)

    def _check_database(self) -> bool:
        if not self.database_path.is_file():
            return False

        try:
            with sqlite3.connect(self.database_path) as connection:
                tables = {
                    row[0]
                    for row in connection.execute(
                        """
                        SELECT name
                        FROM sqlite_master
                        WHERE type = 'table'
                        """
                    )
                }
        except sqlite3.Error:
            return False

        return {"words", "word_indices"}.issubset(tables)

    def _query_text(
        self, connection: sqlite3.Connection, text: str
    ) -> sqlite3.Row | None:
        row = self._query_exact_text(connection, text)
        if row is None:
            row = self._query_index(connection, text)
        if row is None:
            row = self._query_fuzzy_index(connection, text)
        return row

    def _pronounce_text(self, text: str) -> str:
        return "".join(item["hira"] for item in self._kakasi.convert(text))

    def _query_exact_text(
        self, connection: sqlite3.Connection, text: str
    ) -> sqlite3.Row | None:
        return connection.execute(
            """
            SELECT text, pronounce, explanations_json
            FROM words
            WHERE text = ?
            ORDER BY id
            LIMIT 1
            """,
            (text,),
        ).fetchone()

    def _query_index(
        self, connection: sqlite3.Connection, text: str
    ) -> sqlite3.Row | None:
        return connection.execute(
            """
            SELECT words.text, words.pronounce, words.explanations_json
            FROM word_indices
            JOIN words ON words.id = word_indices.word_id
            WHERE word_indices.value = ?
            ORDER BY
                CASE word_indices.kind
                    WHEN 'text' THEN 0
                    WHEN 'pronounce' THEN 1
                    WHEN 'okurigana' THEN 2
                    ELSE 3
                END,
                words.id
            LIMIT 1
            """,
            (text,),
        ).fetchone()

    def _query_fuzzy_index(
        self, connection: sqlite3.Connection, text: str
    ) -> sqlite3.Row | None:
        return connection.execute(
            """
            SELECT words.text, words.pronounce, words.explanations_json
            FROM word_indices
            JOIN words ON words.id = word_indices.word_id
            WHERE word_indices.value LIKE ?
            ORDER BY
                LENGTH(word_indices.value),
                CASE word_indices.kind
                    WHEN 'text' THEN 0
                    WHEN 'pronounce' THEN 1
                    WHEN 'okurigana' THEN 2
                    ELSE 3
                END,
                words.id
            LIMIT 1
            """,
            (f"%{text}%",),
        ).fetchone()

    def _row_to_word(self, row: sqlite3.Row) -> DictWord:
        return DictWord(
            text=row["text"],
            pronounce=row["pronounce"],
            explanations=json.loads(row["explanations_json"]),
        )
