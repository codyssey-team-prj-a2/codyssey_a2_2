"""Tests for cleaner.py: text normalization, date normalization, required fields."""

import unittest

import cleaner


class TestCleaner(unittest.TestCase):
    def test_normalize_text_strips_html_and_whitespace(self) -> None:
        raw = "<p>Hello   <b>World</b></p>\n\n  extra   spaces "
        result = cleaner.normalize_text(raw)
        self.assertEqual(result, "Hello World extra spaces")

    def test_normalize_text_truncates_long_text(self) -> None:
        raw = "가" * 100
        result = cleaner.normalize_text(raw, max_length=10)
        self.assertTrue(result.endswith("..."))
        self.assertLessEqual(len(result), 13)

    def test_normalize_date_rfc822(self) -> None:
        result = cleaner.normalize_date("Sat, 01 Aug 2026 09:00:00 +0900")
        self.assertRegex(result, r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")

    def test_normalize_date_iso(self) -> None:
        result = cleaner.normalize_date("2026-08-01T09:00:00Z")
        self.assertRegex(result, r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")

    def test_normalize_date_invalid_returns_none(self) -> None:
        self.assertIsNone(cleaner.normalize_date("not-a-date"))
        self.assertIsNone(cleaner.normalize_date(None))

    def test_validate_required_fields_missing(self) -> None:
        missing = cleaner.validate_required_fields({"title": "t", "url": None, "published_at": "2026-08-01"})
        self.assertIn("url", missing)

    def test_clean_article_fails_without_required_fields(self) -> None:
        article = {"id": 1, "title": None, "url": "https://x.com", "published_at": "2026-08-01"}
        self.assertIsNone(cleaner.clean_article(article))

    def test_clean_article_success(self) -> None:
        article = {
            "id": 1,
            "title": "  제목  ",
            "description": "설명",
            "content": "본문",
            "url": "https://x.com",
            "published_at": "2026-08-01T09:00:00Z",
            "source": None,
            "category": None,
        }
        result = cleaner.clean_article(article)
        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "제목")
        self.assertEqual(result["source"], "Unknown")
        self.assertEqual(result["status"], "clean")


if __name__ == "__main__":
    unittest.main()
