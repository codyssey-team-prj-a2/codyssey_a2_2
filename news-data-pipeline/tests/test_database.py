"""Tests for database.py: connection, insert, duplicate handling."""

import tempfile
import unittest
from pathlib import Path

import database


def make_article(url: str = "https://example.com/a") -> dict:
    return {
        "title": "테스트 뉴스",
        "description": "설명",
        "content": "본문",
        "url": url,
        "source": "테스트소스",
        "category": "technology",
        "published_at": "2026-08-01 09:00:00",
        "collected_at": "2026-08-01 09:00:00",
        "collection_method": "test",
    }


class TestDatabase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmpdir.name) / "test.db"
        database.init_db(self.db_path)
        self.conn = database.get_connection(self.db_path)

    def tearDown(self) -> None:
        self.conn.close()
        self._tmpdir.cleanup()

    def test_connection_and_tables_created(self) -> None:
        cursor = self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row["name"] for row in cursor.fetchall()}
        self.assertIn("news", tables)
        self.assertIn("analysis_results", tables)

    def test_insert_article(self) -> None:
        row_id, outcome = database.save_article(self.conn, make_article())
        self.assertEqual(outcome, "inserted")
        row = database.get_article_by_id(self.conn, row_id)
        self.assertEqual(row["title"], "테스트 뉴스")

    def test_duplicate_skip_policy(self) -> None:
        article = make_article()
        database.save_article(self.conn, article, duplicate_policy="skip")
        _, outcome = database.save_article(self.conn, article, duplicate_policy="skip")
        self.assertEqual(outcome, "skipped")
        self.assertEqual(database.count_articles(self.conn), 1)

    def test_duplicate_upsert_policy(self) -> None:
        article = make_article()
        database.save_article(self.conn, article, duplicate_policy="upsert")
        article["title"] = "수정된 제목"
        row_id, outcome = database.save_article(self.conn, article, duplicate_policy="upsert")
        self.assertEqual(outcome, "updated")
        row = database.get_article_by_id(self.conn, row_id)
        self.assertEqual(row["title"], "수정된 제목")
        self.assertEqual(database.count_articles(self.conn), 1)


if __name__ == "__main__":
    unittest.main()
