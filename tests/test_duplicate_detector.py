import os
import sys
import unittest
import tempfile
import shutil
from unittest.mock import patch, MagicMock

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from duplicate_detector import DuplicateDetector


class TestSanitizeFilename(unittest.TestCase):
    """Unit tests for DuplicateDetector.sanitize_filename."""

    def test_illegal_windows_characters_removed(self):
        illegal_chars = r'AC/DC: Highway to Hell? *Live* <2020> | Special "Edition"'
        cleaned = DuplicateDetector.sanitize_filename(illegal_chars)
        for char in r'\/*?:"<>|':
            self.assertNotIn(char, cleaned)
        self.assertEqual(cleaned, "ACDC Highway to Hell Live 2020 Special Edition")

    def test_whitespace_collapsing_and_stripping(self):
        messy = "   Queen   -   Bohemian   Rhapsody   "
        self.assertEqual(DuplicateDetector.sanitize_filename(messy), "Queen - Bohemian Rhapsody")

    def test_only_illegal_chars_returns_untitled(self):
        self.assertEqual(DuplicateDetector.sanitize_filename(r'\/*?:"<>|'), "untitled")

    def test_empty_or_whitespace_returns_untitled(self):
        self.assertEqual(DuplicateDetector.sanitize_filename(""), "untitled")
        self.assertEqual(DuplicateDetector.sanitize_filename("   "), "untitled")

    def test_valid_filename_preserved(self):
        name = "01. The Weeknd - Blinding Lights (2020)"
        self.assertEqual(DuplicateDetector.sanitize_filename(name), name)


class TestNormalizeText(unittest.TestCase):
    """Unit tests for DuplicateDetector.normalize_text."""

    def test_unicode_accents_decomposed(self):
        self.assertEqual(DuplicateDetector.normalize_text("Café del Mar"), "cafe del mar")
        self.assertEqual(DuplicateDetector.normalize_text("Beyoncé"), "beyonce")
        self.assertEqual(DuplicateDetector.normalize_text("Motörhead"), "motorhead")

    def test_parenthetical_tags_removed(self):
        self.assertEqual(DuplicateDetector.normalize_text("Blinding Lights (feat. Drake)"), "blinding lights")
        self.assertEqual(DuplicateDetector.normalize_text("Starboy [Official Music Video]"), "starboy")
        self.assertEqual(DuplicateDetector.normalize_text("In the End {Live in Texas}"), "in the end")

    def test_punctuation_and_special_symbols_removed(self):
        self.assertEqual(DuplicateDetector.normalize_text("Don't Stop Believin'!"), "don t stop believin")
        self.assertEqual(DuplicateDetector.normalize_text("Rock & Roll"), "rock roll")

    def test_whitespace_collapsed(self):
        self.assertEqual(DuplicateDetector.normalize_text("  hello    world  "), "hello world")

    def test_empty_or_none(self):
        self.assertEqual(DuplicateDetector.normalize_text(""), "")
        self.assertEqual(DuplicateDetector.normalize_text(None), "")


class TestSimilarityRatio(unittest.TestCase):
    """Unit tests for DuplicateDetector.similarity_ratio."""

    def test_identical_strings_equal_one(self):
        self.assertAlmostEqual(DuplicateDetector.similarity_ratio("hello", "hello"), 1.0)

    def test_minor_difference_high_ratio(self):
        ratio = DuplicateDetector.similarity_ratio("blinding lights", "blinding light")
        self.assertGreater(ratio, 0.90)

    def test_completely_different_low_ratio(self):
        ratio = DuplicateDetector.similarity_ratio("hotel california", "shape of you")
        self.assertLess(ratio, 0.35)


class TestFormatFileSize(unittest.TestCase):
    """Unit tests for DuplicateDetector.format_file_size."""

    def test_bytes_formatting(self):
        self.assertEqual(DuplicateDetector.format_file_size(500), "500 B")
        self.assertEqual(DuplicateDetector.format_file_size(0), "0 B")

    def test_kilobytes_formatting(self):
        self.assertEqual(DuplicateDetector.format_file_size(1024), "1.0 KB")
        self.assertEqual(DuplicateDetector.format_file_size(1536), "1.5 KB")

    def test_megabytes_formatting(self):
        self.assertEqual(DuplicateDetector.format_file_size(1024 * 1024), "1.00 MB")
        self.assertEqual(DuplicateDetector.format_file_size(5 * 1024 * 1024), "5.00 MB")
        self.assertEqual(DuplicateDetector.format_file_size(10485760), "10.00 MB")


class TestDuplicateDetectorFileMatching(unittest.TestCase):
    """Integration-style tests for DuplicateDetector with temporary directory and files."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="beatvault_test_dup_")
        self.detector = DuplicateDetector(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_nonexistent_directory_handled_safely(self):
        det = DuplicateDetector(os.path.join(self.test_dir, "nonexistent_subfolder"))
        self.assertEqual(det._cache, {})
        result = det.check_duplicate("Test Song", "Test Artist")
        self.assertIsNone(result)

    def test_exact_filename_duplicate_found(self):
        file_path = os.path.join(self.test_dir, "Queen - Bohemian Rhapsody.mp3")
        with open(file_path, "wb") as f:
            f.write(b"MOCK_MP3_DATA" * 100)

        self.detector.refresh_cache()
        dup = self.detector.check_duplicate("Bohemian Rhapsody", "Queen")

        self.assertIsNotNone(dup)
        self.assertTrue(dup["is_duplicate"])
        self.assertEqual(dup["match_type"], "filename_exact")
        self.assertEqual(dup["existing_file_name"], "Queen - Bohemian Rhapsody.mp3")
        self.assertEqual(dup["existing_file_path"], file_path)
        self.assertGreater(dup["existing_file_bytes"], 0)

    def test_fuzzy_filename_duplicate_found(self):
        file_path = os.path.join(self.test_dir, "Bohemian Rhapsody (2011 Remaster).mp3")
        with open(file_path, "wb") as f:
            f.write(b"MOCK_MP3_DATA" * 100)

        self.detector.refresh_cache()
        dup = self.detector.check_duplicate("Bohemian Rhapsody", "Queen")

        self.assertIsNotNone(dup)
        self.assertTrue(dup["is_duplicate"])
        self.assertEqual(dup["match_type"], "filename_fuzzy")
        self.assertGreaterEqual(dup["match_confidence"], 0.83)

    def test_no_duplicate_returns_none(self):
        file_path = os.path.join(self.test_dir, "Led Zeppelin - Stairway to Heaven.mp3")
        with open(file_path, "wb") as f:
            f.write(b"MOCK_MP3_DATA" * 100)

        self.detector.refresh_cache()
        dup = self.detector.check_duplicate("Bohemian Rhapsody", "Queen")
        self.assertIsNone(dup)

    @patch("duplicate_detector.EasyID3")
    def test_id3_tag_duplicate_match(self, mock_easyid3):
        file_path = os.path.join(self.test_dir, "track01_unknown.mp3")
        with open(file_path, "wb") as f:
            f.write(b"MOCK_MP3_DATA" * 100)

        mock_instance = MagicMock()
        mock_instance.get.side_effect = lambda key, default: {
            "title": ["Blinding Lights"],
            "artist": ["The Weeknd"]
        }.get(key, default)
        mock_easyid3.return_value = mock_instance

        self.detector.refresh_cache()
        dup = self.detector.check_duplicate("Blinding Lights", "The Weeknd")

        self.assertIsNotNone(dup)
        self.assertTrue(dup["is_duplicate"])
        self.assertEqual(dup["match_type"], "id3_tags")
        self.assertIn("Blinding Lights", dup["reason"])


class TestDestinationFilenameTemplates(unittest.TestCase):
    """Tests for naming templates and incremental filename collision handling."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="beatvault_test_tpl_")
        self.detector = DuplicateDetector(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_template_title_artist_default(self):
        full_path, name = self.detector.get_destination_filename("Yesterday", "The Beatles")
        self.assertEqual(name, "Yesterday - The Beatles.mp3")
        self.assertEqual(full_path, os.path.join(self.test_dir, name))

    def test_template_title_artist_without_artist(self):
        full_path, name = self.detector.get_destination_filename("Yesterday", "")
        self.assertEqual(name, "Yesterday.mp3")

    def test_template_artist_title(self):
        full_path, name = self.detector.get_destination_filename(
            "Yesterday", "The Beatles", template="artist_title"
        )
        self.assertEqual(name, "The Beatles - Yesterday.mp3")

    def test_template_track_title_artist(self):
        full_path, name = self.detector.get_destination_filename(
            "Yesterday", "The Beatles", track_index=1, template="track_title_artist"
        )
        self.assertEqual(name, "01. Yesterday - The Beatles.mp3")

        full_path, name = self.detector.get_destination_filename(
            "Yesterday", "The Beatles", track_index=14, template="track_title_artist"
        )
        self.assertEqual(name, "14. Yesterday - The Beatles.mp3")

    def test_template_title_only(self):
        full_path, name = self.detector.get_destination_filename(
            "Yesterday", "The Beatles", template="title_only"
        )
        self.assertEqual(name, "Yesterday.mp3")

    def test_collision_allow_copy_increments_suffix(self):
        base_name = "Yesterday - The Beatles.mp3"
        base_path = os.path.join(self.test_dir, base_name)
        with open(base_path, "wb") as f:
            f.write(b"existing")

        # First collision -> (1)
        path1, name1 = self.detector.get_destination_filename("Yesterday", "The Beatles", allow_copy=True)
        self.assertEqual(name1, "Yesterday - The Beatles (1).mp3")

        # Create that file too
        with open(path1, "wb") as f:
            f.write(b"existing 1")

        # Second collision -> (2)
        path2, name2 = self.detector.get_destination_filename("Yesterday", "The Beatles", allow_copy=True)
        self.assertEqual(name2, "Yesterday - The Beatles (2).mp3")

    def test_collision_without_allow_copy_returns_same_path(self):
        base_name = "Yesterday - The Beatles.mp3"
        base_path = os.path.join(self.test_dir, base_name)
        with open(base_path, "wb") as f:
            f.write(b"existing")

        path, name = self.detector.get_destination_filename("Yesterday", "The Beatles", allow_copy=False)
        self.assertEqual(name, base_name)
        self.assertEqual(path, base_path)


if __name__ == "__main__":
    unittest.main()
