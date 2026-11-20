import os
import sys
import json
import unittest
import tempfile
import shutil
from unittest.mock import patch, MagicMock

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api import AppAPI


class TestApiSettingsPersistence(unittest.TestCase):
    """Tests for AppAPI settings.json read, write, and default fallback handling."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="beatvault_test_api_")
        self.config_path = os.path.join(self.test_dir, "settings.json")
        self.api = AppAPI()
        # Patch config path to our isolated temp file
        self.patcher = patch.object(self.api, "_get_config_path", return_value=self.config_path)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_get_settings_default_fallback_when_file_missing(self):
        res = self.api.get_settings()
        self.assertTrue(res["success"])
        settings = res["settings"]

        self.assertEqual(settings["concurrency"], 2)
        self.assertEqual(settings["audio_quality"], "192")
        self.assertEqual(settings["filename_template"], "title_artist")
        self.assertTrue(settings["embed_lyrics"])
        self.assertFalse(settings["auto_skip_duplicates"])
        self.assertEqual(settings["theme_accent"], "green")
        self.assertTrue(os.path.exists(settings["destination_folder"]))

    def test_save_and_retrieve_settings(self):
        new_settings = {
            "concurrency": 4,
            "audio_quality": "320",
            "filename_template": "artist_title",
            "theme_accent": "purple"
        }
        save_res = self.api.save_settings(new_settings)
        self.assertTrue(save_res["success"])
        self.assertEqual(save_res["settings"]["concurrency"], 4)
        self.assertEqual(save_res["settings"]["audio_quality"], "320")
        self.assertEqual(save_res["settings"]["theme_accent"], "purple")

        # Verify on-disk file was written
        self.assertTrue(os.path.exists(self.config_path))
        with open(self.config_path, "r", encoding="utf-8") as f:
            disk_data = json.load(f)
        self.assertEqual(disk_data["concurrency"], 4)
        self.assertEqual(disk_data["theme_accent"], "purple")

        # Verify get_settings reads the updated values
        get_res = self.api.get_settings()
        self.assertTrue(get_res["success"])
        self.assertEqual(get_res["settings"]["concurrency"], 4)
        self.assertEqual(get_res["settings"]["theme_accent"], "purple")
        # Defaults for unmentioned fields still preserved
        self.assertTrue(get_res["settings"]["embed_lyrics"])

    def test_corrupted_settings_file_recovers_to_defaults(self):
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write("{ INVALID JSON CONTENT :::")

        res = self.api.get_settings()
        self.assertTrue(res["success"])
        self.assertEqual(res["settings"]["concurrency"], 2)
        self.assertEqual(res["settings"]["theme_accent"], "green")


class TestConcurrencyClamping(unittest.TestCase):
    """Tests for concurrency value clamping (strictly between 1 and 8)."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="beatvault_test_clamp_")
        self.api = AppAPI()
        self.sample_tracks = [{"title": "Song", "artist": "Artist", "index": 1}]

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch("downloader.DownloadWorker.run")
    @patch("downloader.DownloadWorker.__init__", return_value=None)
    def test_concurrency_clamped_below_min(self, mock_worker_init, mock_run):
        # 0 or negative must clamp to 1
        for val in [0, -1, -10]:
            self.api.current_worker = None
            self.api.start_download(
                tracks=self.sample_tracks,
                destination_folder=self.test_dir,
                concurrency=val
            )
            kwargs = mock_worker_init.call_args.kwargs
            self.assertEqual(kwargs["max_concurrency"], 1)

    @patch("downloader.DownloadWorker.run")
    @patch("downloader.DownloadWorker.__init__", return_value=None)
    def test_concurrency_clamped_above_max(self, mock_worker_init, mock_run):
        # Above 8 must clamp to 8
        for val in [9, 10, 32, 100]:
            self.api.current_worker = None
            self.api.start_download(
                tracks=self.sample_tracks,
                destination_folder=self.test_dir,
                concurrency=val
            )
            kwargs = mock_worker_init.call_args.kwargs
            self.assertEqual(kwargs["max_concurrency"], 8)

    @patch("downloader.DownloadWorker.run")
    @patch("downloader.DownloadWorker.__init__", return_value=None)
    def test_concurrency_valid_in_range(self, mock_worker_init, mock_run):
        for val in [1, 2, 4, 7, 8]:
            self.api.current_worker = None
            self.api.start_download(
                tracks=self.sample_tracks,
                destination_folder=self.test_dir,
                concurrency=val
            )
            kwargs = mock_worker_init.call_args.kwargs
            self.assertEqual(kwargs["max_concurrency"], val)

    @patch("downloader.DownloadWorker.run")
    @patch("downloader.DownloadWorker.__init__", return_value=None)
    def test_concurrency_string_and_invalid_type_fallback(self, mock_worker_init, mock_run):
        # String representations of valid integers
        self.api.current_worker = None
        self.api.start_download(
            tracks=self.sample_tracks,
            destination_folder=self.test_dir,
            concurrency="5"
        )
        self.assertEqual(mock_worker_init.call_args.kwargs["max_concurrency"], 5)

        # Invalid string or non-numeric type falls back to default 2
        for invalid in ["abc", None, [], {}]:
            self.api.current_worker = None
            self.api.start_download(
                tracks=self.sample_tracks,
                destination_folder=self.test_dir,
                concurrency=invalid
            )
            self.assertEqual(mock_worker_init.call_args.kwargs["max_concurrency"], 2)


class TestApiDownloadValidationAndDuplicates(unittest.TestCase):
    """Tests for input validation and duplicate responses in AppAPI."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="beatvault_test_val_")
        self.api = AppAPI()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_empty_tracks_rejected(self):
        res = self.api.start_download(tracks=[], destination_folder=self.test_dir)
        self.assertFalse(res["success"])
        self.assertIn("No tracks to download", res["error"])

    def test_missing_destination_folder_rejected(self):
        res = self.api.start_download(
            tracks=[{"title": "Track", "artist": "Artist"}],
            destination_folder=""
        )
        self.assertFalse(res["success"])
        self.assertIn("choose a download folder", res["error"])

    def test_already_active_download_rejected(self):
        mock_worker = MagicMock()
        mock_worker.stats = {"is_active": True}
        self.api.current_worker = mock_worker

        res = self.api.start_download(
            tracks=[{"title": "Track", "artist": "Artist"}],
            destination_folder=self.test_dir
        )
        self.assertFalse(res["success"])
        self.assertIn("already active", res["error"])

    def test_respond_duplicate_without_active_worker(self):
        self.api.current_worker = None
        res = self.api.respond_duplicate("skip")
        self.assertFalse(res["success"])
        self.assertIn("No active worker", res["error"])

    def test_respond_duplicate_forwards_to_worker(self):
        mock_worker = MagicMock()
        self.api.current_worker = mock_worker

        res = self.api.respond_duplicate("download_again", apply_to_all=True)
        self.assertTrue(res["success"])
        mock_worker.provide_duplicate_decision.assert_called_once_with("download_again", True)


if __name__ == "__main__":
    unittest.main()
