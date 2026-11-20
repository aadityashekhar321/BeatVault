import os
import sys
import unittest
import tempfile
import shutil
import threading
import time
from unittest.mock import patch, MagicMock

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from downloader import DownloadWorker
from duplicate_detector import DuplicateDetector


class TestDownloaderFilenameSanitizerAndTemplates(unittest.TestCase):
    """Tests for filename sanitization and template formatting within downloader flow."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="beatvault_test_dl_tpl_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_sanitizes_illegal_windows_characters_in_track(self):
        detector = DuplicateDetector(self.test_dir)
        full_path, name = detector.get_destination_filename(
            title="Song: Live *2024*?",
            artist='AC/DC "Special" | Edition',
            template="title_artist"
        )
        for char in r'\/*?:"<>|':
            self.assertNotIn(char, name)
        self.assertIn("Song Live 2024", name)
        self.assertIn("ACDC Special Edition", name)

    def test_all_filename_templates(self):
        detector = DuplicateDetector(self.test_dir)
        title = "Blinding Lights"
        artist = "The Weeknd"

        # title_artist (default)
        _, name = detector.get_destination_filename(title, artist, template="title_artist")
        self.assertEqual(name, "Blinding Lights - The Weeknd.mp3")

        # artist_title
        _, name = detector.get_destination_filename(title, artist, template="artist_title")
        self.assertEqual(name, "The Weeknd - Blinding Lights.mp3")

        # track_title_artist
        _, name = detector.get_destination_filename(title, artist, track_index=7, template="track_title_artist")
        self.assertEqual(name, "07. Blinding Lights - The Weeknd.mp3")

        # title_only
        _, name = detector.get_destination_filename(title, artist, template="title_only")
        self.assertEqual(name, "Blinding Lights.mp3")


class TestDownloadWorkerQueue(unittest.TestCase):
    """Tests for DownloadWorker thread queue execution, state transitions, and callbacks."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="beatvault_test_queue_")
        self.sample_tracks = [
            {
                "index": 1,
                "id": "t1",
                "title": "Song One",
                "artist": "Artist A",
                "duration_ms": 180000,
                "status": "queued",
                "status_message": "Ready",
                "progress": 0,
                "selected": True,
                "duplicate_info": None
            },
            {
                "index": 2,
                "id": "t2",
                "title": "Song Two",
                "artist": "Artist B",
                "duration_ms": 210000,
                "status": "queued",
                "status_message": "Ready",
                "progress": 0,
                "selected": True,
                "duplicate_info": None
            }
        ]

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_worker_initialization_defaults(self):
        worker = DownloadWorker(
            tracks=self.sample_tracks,
            destination_folder=self.test_dir
        )
        self.assertEqual(worker.stats["total"], 2)
        self.assertEqual(worker.stats["completed"], 0)
        self.assertEqual(worker.stats["failed"], 0)
        self.assertEqual(worker.stats["skipped"], 0)
        self.assertFalse(worker.stats["is_active"])
        self.assertFalse(worker.stats["is_paused"])
        self.assertFalse(worker.stats["is_cancelled"])

    def test_worker_pause_and_resume(self):
        worker = DownloadWorker(tracks=[], destination_folder=self.test_dir)
        self.assertTrue(worker._pause_event.is_set())

        worker.pause()
        self.assertFalse(worker._pause_event.is_set())
        self.assertTrue(worker.stats["is_paused"])

        worker.resume()
        self.assertTrue(worker._pause_event.is_set())
        self.assertFalse(worker.stats["is_paused"])

    def test_worker_cancel(self):
        worker = DownloadWorker(tracks=[], destination_folder=self.test_dir)
        self.assertFalse(worker._stop_event.is_set())

        worker.cancel()
        self.assertTrue(worker._stop_event.is_set())
        self.assertTrue(worker._pause_event.is_set())
        self.assertTrue(worker.stats["is_cancelled"])

    @patch.object(DownloadWorker, "_download_and_convert", return_value=True)
    def test_worker_processes_tracks_to_completion(self, mock_dl):
        completed_events = []
        progress_events = []
        finished_stats = []

        def on_track_complete(payload):
            completed_events.append(payload["track"]["id"])

        def on_progress(payload):
            progress_events.append(payload["percent"])

        def on_finished(stats):
            finished_stats.append(dict(stats))

        worker = DownloadWorker(
            tracks=self.sample_tracks,
            destination_folder=self.test_dir,
            max_concurrency=2,
            on_progress=on_progress,
            on_track_complete=on_track_complete,
            on_finished=on_finished
        )

        worker.run()

        self.assertEqual(worker.stats["completed"], 2)
        self.assertEqual(worker.stats["failed"], 0)
        self.assertEqual(worker.stats["skipped"], 0)
        self.assertFalse(worker.stats["is_active"])
        self.assertEqual(len(completed_events), 2)
        self.assertIn("t1", completed_events)
        self.assertIn("t2", completed_events)
        self.assertTrue(len(progress_events) > 0)
        self.assertEqual(len(finished_stats), 1)
        self.assertEqual(finished_stats[0]["completed"], 2)

    @patch.object(DownloadWorker, "_download_and_convert", return_value=False)
    def test_worker_handles_download_failures(self, mock_dl):
        worker = DownloadWorker(
            tracks=self.sample_tracks,
            destination_folder=self.test_dir
        )
        worker.run()

        self.assertEqual(worker.stats["failed"], 2)
        self.assertEqual(worker.stats["completed"], 0)
        self.assertEqual(self.sample_tracks[0]["status"], "failed")

    @patch.object(DownloadWorker, "_download_and_convert", return_value=True)
    def test_worker_duplicate_prompt_and_skip(self, mock_dl):
        # Create an existing file so duplicate is detected
        existing_file = os.path.join(self.test_dir, "Song One - Artist A.mp3")
        with open(existing_file, "wb") as f:
            f.write(b"existing")

        duplicate_reported = threading.Event()

        def on_duplicate(track, dup_info):
            # Respond to duplicate by skipping
            duplicate_reported.set()
            worker.provide_duplicate_decision("skip")

        worker = DownloadWorker(
            tracks=[self.sample_tracks[0]],
            destination_folder=self.test_dir,
            on_duplicate_detected=on_duplicate
        )

        worker.run()

        self.assertTrue(duplicate_reported.is_set())
        self.assertEqual(worker.stats["duplicates"], 1)
        self.assertEqual(worker.stats["skipped"], 1)
        self.assertEqual(worker.stats["completed"], 0)
        self.assertEqual(self.sample_tracks[0]["status"], "skipped")

    @patch.object(DownloadWorker, "_download_and_convert", return_value=True)
    def test_worker_duplicate_apply_to_all_download_again(self, mock_dl):
        # Create existing files for both tracks
        file1 = os.path.join(self.test_dir, "Song One - Artist A.mp3")
        file2 = os.path.join(self.test_dir, "Song Two - Artist B.mp3")
        with open(file1, "wb") as f:
            f.write(b"existing1")
        with open(file2, "wb") as f:
            f.write(b"existing2")

        prompt_counts = 0
        prompt_lock = threading.Lock()

        def on_duplicate(track, dup_info):
            nonlocal prompt_counts
            with prompt_lock:
                prompt_counts += 1
            # Apply download_again to all
            worker.provide_duplicate_decision("download_again", apply_to_all=True)

        worker = DownloadWorker(
            tracks=self.sample_tracks,
            destination_folder=self.test_dir,
            max_concurrency=1,
            on_duplicate_detected=on_duplicate
        )

        worker.run()

        # Because apply_to_all is True, subsequent tracks reuse decision without re-prompting
        self.assertEqual(prompt_counts, 1)
        self.assertEqual(worker.stats["duplicates"], 2)
        self.assertEqual(worker.stats["completed"], 2)


class TestSmartDurationMatcher(unittest.TestCase):
    """Tests for DownloadWorker._smart_find_source logic."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="beatvault_test_smart_")
        self.worker = DownloadWorker(tracks=[], destination_folder=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_returns_direct_source_url_if_present(self):
        track = {
            "title": "Direct Song",
            "artist": "Direct Artist",
            "direct_source_url": "https://www.youtube.com/watch?v=direct123"
        }
        res = self.worker._smart_find_source(track)
        self.assertEqual(res, "https://www.youtube.com/watch?v=direct123")

    def test_short_duration_uses_fallback_query(self):
        track = {
            "title": "Short Jingle",
            "artist": "Advertiser",
            "duration_ms": 10000  # 10s < 15s
        }
        res = self.worker._smart_find_source(track)
        self.assertEqual(res, "ytsearch1:Advertiser - Short Jingle audio")

    @patch("yt_dlp.YoutubeDL")
    def test_smart_matching_picks_candidate_with_closest_duration(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        # Target duration: 200s (200,000 ms)
        # Candidates: 180s (diff 20), 202s (diff 2), 250s (diff 50)
        mock_ydl.extract_info.return_value = {
            "entries": [
                {"title": "Song Title live", "duration": 200, "id": "unwanted_live"},
                {"title": "Song Title", "duration": 180, "id": "cand1"},
                {"title": "Song Title Audio", "duration": 202, "id": "cand_best", "url": "https://youtube.com/watch?v=cand_best"},
                {"title": "Song Title", "duration": 250, "id": "cand3"}
            ]
        }
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl

        track = {
            "title": "Song Title",
            "artist": "Artist Name",
            "duration_ms": 200000
        }
        res = self.worker._smart_find_source(track)
        self.assertEqual(res, "https://youtube.com/watch?v=cand_best")


if __name__ == "__main__":
    unittest.main()
