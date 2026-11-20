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

from lyrics_service import LyricsService


class TestLyricsCleanText(unittest.TestCase):
    """Tests for LyricsService.clean_text."""

    def test_strips_parentheticals_and_tags(self):
        self.assertEqual(LyricsService.clean_text("Blinding Lights (feat. Drake)"), "Blinding Lights")
        self.assertEqual(LyricsService.clean_text("Starboy [Official Audio]"), "Starboy")
        self.assertEqual(LyricsService.clean_text("Song Title {Remastered 2020}"), "Song Title")

    def test_preserves_clean_text(self):
        self.assertEqual(LyricsService.clean_text("Bohemian Rhapsody"), "Bohemian Rhapsody")

    def test_handles_empty_or_none(self):
        self.assertEqual(LyricsService.clean_text(""), "")
        self.assertEqual(LyricsService.clean_text(None), "")


class TestLrcTimecodeParser(unittest.TestCase):
    """Tests for LyricsService.parse_timecode and parse_lrc."""

    def test_parse_timecode_two_digit_ms(self):
        self.assertEqual(LyricsService.parse_timecode("[01:23.45]"), 83.45)
        self.assertEqual(LyricsService.parse_timecode("01:23.45"), 83.45)

    def test_parse_timecode_three_digit_ms(self):
        self.assertEqual(LyricsService.parse_timecode("[00:05.500]"), 5.5)
        self.assertEqual(LyricsService.parse_timecode("[02:10.050]"), 130.05)

    def test_parse_timecode_zero_and_start(self):
        self.assertEqual(LyricsService.parse_timecode("[00:00.00]"), 0.0)

    def test_parse_timecode_invalid_format(self):
        self.assertIsNone(LyricsService.parse_timecode("invalid"))
        self.assertIsNone(LyricsService.parse_timecode(""))
        self.assertIsNone(LyricsService.parse_timecode(None))

    def test_parse_lrc_full_structured_output(self):
        lrc_content = """
        [ti:Blinding Lights]
        [ar:The Weeknd]
        [al:After Hours]
        [00:05.20]Yeah
        [00:15.80]I've been on my own for long enough
        [00:22.45]Maybe you can show me how to love
        """
        parsed = LyricsService.parse_lrc(lrc_content)
        self.assertEqual(len(parsed), 3)

        self.assertEqual(parsed[0]["time"], 5.20)
        self.assertEqual(parsed[0]["text"], "Yeah")

        self.assertEqual(parsed[1]["time"], 15.80)
        self.assertEqual(parsed[1]["text"], "I've been on my own for long enough")

        self.assertEqual(parsed[2]["time"], 22.45)
        self.assertEqual(parsed[2]["text"], "Maybe you can show me how to love")

    def test_parse_lrc_multiple_timestamps_single_line(self):
        lrc_content = "[00:10.50][00:20.50]Repeated chorus verse"
        parsed = LyricsService.parse_lrc(lrc_content)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["time"], 10.50)
        self.assertEqual(parsed[0]["text"], "Repeated chorus verse")
        self.assertEqual(parsed[1]["time"], 20.50)
        self.assertEqual(parsed[1]["text"], "Repeated chorus verse")

    def test_parse_lrc_sorts_out_of_order_lines(self):
        lrc_content = """
        [00:30.00]Line three
        [00:10.00]Line one
        [00:20.00]Line two
        """
        parsed = LyricsService.parse_lrc(lrc_content)
        times = [entry["time"] for entry in parsed]
        self.assertEqual(times, [10.0, 20.0, 30.0])

    def test_parse_lrc_empty_or_no_tags(self):
        self.assertEqual(LyricsService.parse_lrc(""), [])
        self.assertEqual(LyricsService.parse_lrc("Just plain lyrics without tags\nSecond line"), [])
        self.assertEqual(LyricsService.parse_lrc(None), [])


class TestFetchLyrics(unittest.TestCase):
    """Tests for LyricsService.fetch_lyrics API calls with requests mocking."""

    @patch("requests.get")
    def test_fetch_lyrics_direct_get_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "plainLyrics": "Plain lyrics line 1\nPlain lyrics line 2",
            "syncedLyrics": "[00:05.00]Line 1\n[00:10.00]Line 2"
        }
        mock_get.return_value = mock_resp

        lyrics = LyricsService.fetch_lyrics("Blinding Lights", "The Weeknd", duration_sec=200)

        self.assertIsNotNone(lyrics)
        self.assertIn("Plain lyrics line 1", lyrics["plain"])
        self.assertIn("[00:05.00]Line 1", lyrics["synced"])
        mock_get.assert_called_once()
        called_args, called_kwargs = mock_get.call_args
        self.assertIn("/get", called_args[0])
        self.assertEqual(called_kwargs["params"]["track_name"], "Blinding Lights")
        self.assertEqual(called_kwargs["params"]["duration"], 200)

    @patch("requests.get")
    def test_fetch_lyrics_search_fallback(self, mock_get):
        # 1st call to /get returns 404; 2nd call to /search returns results list
        resp_404 = MagicMock()
        resp_404.status_code = 404

        resp_search = MagicMock()
        resp_search.status_code = 200
        resp_search.json.return_value = [
            {
                "plainLyrics": "Found via search",
                "syncedLyrics": "[00:01.00]Found via search"
            }
        ]
        mock_get.side_effect = [resp_404, resp_search]

        lyrics = LyricsService.fetch_lyrics("Uncommon Track", "Indie Artist")
        self.assertIsNotNone(lyrics)
        self.assertEqual(lyrics["plain"], "Found via search")
        self.assertEqual(lyrics["synced"], "[00:01.00]Found via search")
        self.assertEqual(mock_get.call_count, 2)

    @patch("requests.get")
    def test_fetch_lyrics_both_fail_returns_none(self, mock_get):
        resp_404 = MagicMock()
        resp_404.status_code = 404
        mock_get.return_value = resp_404

        lyrics = LyricsService.fetch_lyrics("Nonexistent Song", "Nobody")
        self.assertIsNone(lyrics)

    @patch("requests.get", side_effect=Exception("Connection timed out"))
    def test_fetch_lyrics_exception_handled_gracefully(self, mock_get):
        lyrics = LyricsService.fetch_lyrics("Any Song", "Any Artist")
        self.assertIsNone(lyrics)


class TestEmbedLyricsToMp3(unittest.TestCase):
    """Tests for embedding lyrics in ID3 tags and writing .lrc sidecar files."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="beatvault_test_lrc_")
        self.mp3_path = os.path.join(self.test_dir, "test_track.mp3")
        with open(self.mp3_path, "wb") as f:
            f.write(b"MOCK_MP3_DATA" * 50)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_nonexistent_mp3_returns_false(self):
        result = LyricsService.embed_lyrics_to_mp3(
            os.path.join(self.test_dir, "missing.mp3"),
            "Title", "Artist"
        )
        self.assertFalse(result)

    @patch.object(LyricsService, "fetch_lyrics", return_value=None)
    def test_no_lyrics_found_returns_false(self, mock_fetch):
        result = LyricsService.embed_lyrics_to_mp3(self.mp3_path, "Title", "Artist")
        self.assertFalse(result)

    @patch("lyrics_service.MP3")
    @patch.object(LyricsService, "fetch_lyrics")
    def test_embed_lyrics_and_write_lrc_file(self, mock_fetch, mock_mp3_cls):
        mock_fetch.return_value = {
            "plain": "Line 1\nLine 2",
            "synced": "[00:05.00]Line 1\n[00:10.00]Line 2"
        }

        mock_audio = MagicMock()
        mock_audio.tags = MagicMock()
        mock_mp3_cls.return_value = mock_audio

        success = LyricsService.embed_lyrics_to_mp3(
            self.mp3_path,
            title="Blinding Lights",
            artist="The Weeknd",
            save_lrc_file=True
        )

        self.assertTrue(success)
        mock_audio.save.assert_called_once_with(v2_version=3)

        # Verify .lrc file was written in the same directory
        lrc_path = os.path.join(self.test_dir, "test_track.lrc")
        self.assertTrue(os.path.exists(lrc_path))
        with open(lrc_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("[00:05.00]Line 1", content)

    @patch("lyrics_service.MP3")
    @patch.object(LyricsService, "fetch_lyrics")
    def test_embed_lyrics_without_saving_lrc_file(self, mock_fetch, mock_mp3_cls):
        mock_fetch.return_value = {
            "plain": "Plain lyrics",
            "synced": "[00:05.00]Synced lyrics"
        }
        mock_audio = MagicMock()
        mock_audio.tags = MagicMock()
        mock_mp3_cls.return_value = mock_audio

        success = LyricsService.embed_lyrics_to_mp3(
            self.mp3_path,
            title="Blinding Lights",
            artist="The Weeknd",
            save_lrc_file=False
        )

        self.assertTrue(success)
        lrc_path = os.path.join(self.test_dir, "test_track.lrc")
        self.assertFalse(os.path.exists(lrc_path))


if __name__ == "__main__":
    unittest.main()
