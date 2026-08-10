"""Tests for exporter.py: CSV/JSONL/Excel output."""

import csv
import json
import tempfile
import unittest
from pathlib import Path

import database
import exporter


class TestExporter(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmpdir.name)
        self.db_path = self.tmp_path / "test.db"
        database.init_db(self.db_path)
        self.conn = database.get_connection(self.db_path)
        database.save_article(
            self.conn,
            {
                "title": "내보내기 테스트",
                "description": "설명",
                "content": "본문",
                "url": "https://example.com/export-test",
                "source": "테스트",
                "category": "technology",
                "published_at": "2026-08-01 09:00:00",
                "collected_at": "2026-08-01 09:00:00",
                "collection_method": "test",
                "status": "clean",
            },
        )

    def tearDown(self) -> None:
        self.conn.close()
        self._tmpdir.cleanup()

    def test_export_to_csv(self) -> None:
        output = self.tmp_path / "out.csv"
        exporter.export_articles(self.conn, "csv", output)
        self.assertTrue(output.exists())
        with open(output, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "내보내기 테스트")

    def test_export_to_jsonl(self) -> None:
        output = self.tmp_path / "out.jsonl"
        exporter.export_articles(self.conn, "jsonl", output)
        lines = output.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1)
        record = json.loads(lines[0])
        self.assertEqual(record["url"], "https://example.com/export-test")

    def test_export_to_xlsx(self) -> None:
        output = self.tmp_path / "out.xlsx"
        exporter.export_articles(self.conn, "xlsx", output)
        self.assertTrue(output.exists())

    def test_export_filters_by_status(self) -> None:
        output = self.tmp_path / "out_filtered.csv"
        exporter.export_articles(self.conn, "csv", output, status="summarized")
        with open(output, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 0)


if __name__ == "__main__":
    unittest.main()
