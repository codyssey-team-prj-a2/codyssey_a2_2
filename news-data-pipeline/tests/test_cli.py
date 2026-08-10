"""Tests for main.py CLI argument parsing."""

import unittest

import main


class TestCliParsing(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = main.build_parser()

    def test_fetch_defaults(self) -> None:
        args = self.parser.parse_args(["fetch"])
        self.assertEqual(args.command, "fetch")
        self.assertIsNone(args.limit)
        self.assertEqual(args.method, "rss")
        self.assertFalse(args.dry_run)

    def test_fetch_with_options(self) -> None:
        args = self.parser.parse_args(["fetch", "--limit", "20", "--category", "technology", "--dry-run"])
        self.assertEqual(args.limit, 20)
        self.assertEqual(args.category, "technology")
        self.assertTrue(args.dry_run)

    def test_summarize_unsummarized_flag(self) -> None:
        args = self.parser.parse_args(["summarize", "--unsummarized"])
        self.assertTrue(args.unsummarized)

    def test_analyze_date_range(self) -> None:
        args = self.parser.parse_args(["analyze", "--start-date", "2026-08-01", "--end-date", "2026-08-09"])
        self.assertEqual(args.start_date, "2026-08-01")
        self.assertEqual(args.end_date, "2026-08-09")

    def test_report_format_choices(self) -> None:
        args = self.parser.parse_args(["report", "--format", "md"])
        self.assertEqual(args.format, "md")
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["report", "--format", "invalid"])

    def test_export_requires_format(self) -> None:
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["export"])
        args = self.parser.parse_args(["export", "--format", "csv"])
        self.assertEqual(args.format, "csv")

    def test_show_requires_id(self) -> None:
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["show"])
        args = self.parser.parse_args(["show", "--id", "5"])
        self.assertEqual(args.id, 5)

    def test_missing_command_errors(self) -> None:
        with self.assertRaises(SystemExit):
            self.parser.parse_args([])


if __name__ == "__main__":
    unittest.main()
