import os
import sys
import json
import base64
import logging
import threading
import requests
from typing import Dict, Any, List, Optional
from platform_service import PlatformService
from duplicate_detector import DuplicateDetector
from downloader import DownloadWorker
from version import __version__, get_version_info
from updater import UpdateChecker, open_release_page, download_release_asset

logger = logging.getLogger("api")

class AppAPI:
    def __init__(self, window=None):
        self.window = window
        self.version = __version__
        self.platform_service = PlatformService()
        self.current_worker: Optional[DownloadWorker] = None
        self.worker_thread: Optional[threading.Thread] = None
        self.tray_service = None
        self.update_checker = UpdateChecker(current_version=__version__)

    def set_window(self, window):
        self.window = window

    def set_tray_service(self, tray_service):
        self.tray_service = tray_service

    def _get_config_path(self) -> str:
        """Returns standard path to persisted settings.json in %APPDATA%/BeatVault."""
        app_data = os.getenv("APPDATA") or os.path.expanduser("~")
        config_dir = os.path.join(app_data, "BeatVault")
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, "settings.json")

    def get_settings(self) -> Dict[str, Any]:
        """Loads persisted user settings, falling back to defaults."""
        default_folder = self.get_default_folder()
        defaults = {
            "concurrency": 2,
            "audio_quality": "192",
            "filename_template": "title_artist",
            "embed_lyrics": True,
            "destination_folder": default_folder,
            "auto_skip_duplicates": False,
            "theme_accent": "green"
        }
        config_file = self._get_config_path()
        if os.path.exists(config_file):
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    defaults.update(saved)
            except Exception as e:
                logger.warning(f"Error reading settings.json: {e}")
        return {"success": True, "settings": defaults, "app_version": self.version}

    def save_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Saves user settings to persisted settings.json."""
        if not isinstance(settings, dict):
            return {"success": False, "error": "Settings must be a dictionary"}
        config_file = self._get_config_path()
        try:
            current_res = self.get_settings()
            current = current_res.get("settings", {})
            current.update(settings)
            os.makedirs(os.path.dirname(config_file), exist_ok=True)
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(current, f, indent=2, ensure_ascii=False)
            return {"success": True, "settings": current}
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            return {"success": False, "error": str(e)}

    def get_default_folder(self) -> str:
        """Returns standard user Music directory, falling back to Downloads."""
        music_dir = os.path.join(os.path.expanduser("~"), "Music", "BeatVault Downloads")
        os.makedirs(music_dir, exist_ok=True)
        return music_dir

    def select_folder(self) -> Optional[str]:
        """Opens native Windows folder selection dialog."""
        # Method 1: Using pywebview window dialog
        if self.window:
            try:
                import webview
                result = self.window.create_file_dialog(webview.FOLDER_DIALOG)
                if result and len(result) > 0:
                    return result[0]
            except Exception as e:
                logger.warning(f"pywebview folder dialog error: {e}")

        # Method 2: Fallback via Tkinter
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            folder = filedialog.askdirectory(title="Select Download Destination Folder")
            root.destroy()
            if folder:
                return folder
        except Exception as e:
            logger.warning(f"Tkinter folder dialog error: {e}")

        return None

    def open_folder(self, folder_path: str) -> bool:
        """Opens the selected folder in Windows File Explorer."""
        if not folder_path or not os.path.exists(folder_path):
            return False
        try:
            os.startfile(os.path.abspath(folder_path))
            return True
        except Exception as e:
            logger.error(f"Failed to open folder: {e}")
            return False

    def load_playlist(self, url: str) -> Dict[str, Any]:
        """
        Parses Spotify, YouTube, Apple Music, or SoundCloud playlist/album URL
        and retrieves tracks metadata.
        """
        if not url or not isinstance(url, str) or not url.strip():
            return {"success": False, "error": "Invalid or empty URL"}
        try:
            data = self.platform_service.fetch_metadata(url.strip())
            return {"success": True, "data": data}
        except Exception as e:
            logger.error(f"Error loading playlist: {e}")
            return {"success": False, "error": str(e)}

    def search_single_song(self, query: str) -> Dict[str, Any]:
        """
        Direct single song search without a playlist link.
        Returns high-quality metadata, album art, and audio preview.
        """
        if not query or not query.strip():
            return {"success": False, "error": "Search query cannot be empty"}

        try:
            resp = requests.get(
                "https://itunes.apple.com/search",
                params={"term": query.strip(), "entity": "song", "limit": 6},
                timeout=6
            )
            if resp.status_code != 200:
                return {"success": False, "error": f"Search returned status {resp.status_code}"}

            results = resp.json().get("results", [])
            tracks = []
            for idx, item in enumerate(results):
                dur_ms = item.get("trackTimeMillis", 0)
                sec = int(dur_ms / 1000)
                dur_fmt = f"{sec // 60}:{sec % 60:02d}" if sec > 0 else "0:00"

                # High-res cover art
                artwork = item.get("artworkUrl100", "")
                if artwork:
                    artwork = artwork.replace("100x100bb", "600x600bb")

                tracks.append({
                    "index": idx + 1,
                    "id": f"direct_{item.get('trackId', idx + 1)}",
                    "title": item.get("trackName", "Unknown Title"),
                    "artist": item.get("artistName", "Unknown Artist"),
                    "album": item.get("collectionName", "Single"),
                    "duration_ms": dur_ms,
                    "duration_formatted": dur_fmt,
                    "cover_url": artwork,
                    "audio_preview": item.get("previewUrl", ""),
                    "status": "queued",
                    "status_message": "Ready",
                    "progress": 0,
                    "selected": True,
                    "duplicate_info": None
                })

            return {"success": True, "tracks": tracks}

        except Exception as e:
            logger.error(f"Direct song search error: {e}")
            return {"success": False, "error": str(e)}

    def get_audio_data(self, file_path: str) -> Dict[str, Any]:
        """
        Reads a local audio file (MP3, FLAC, WAV, M4A, etc.) and returns base64 audio data for the in-app player.
        """
        if not file_path or not isinstance(file_path, str) or not os.path.exists(file_path):
            return {"success": False, "error": "File not found"}

        try:
            ext = os.path.splitext(file_path)[1].lower()
            mime_map = {
                ".mp3": "audio/mpeg",
                ".flac": "audio/flac",
                ".wav": "audio/wav",
                ".m4a": "audio/mp4",
                ".ogg": "audio/ogg",
                ".opus": "audio/opus"
            }
            mime_type = mime_map.get(ext, "audio/mpeg")
            with open(file_path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("utf-8")
            data_uri = f"data:{mime_type};base64,{encoded}"
            return {"success": True, "data_url": data_uri, "mime_type": mime_type}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_lyrics(self, title: str, artist: str = "", duration_sec: Optional[int] = None) -> Dict[str, Any]:
        """
        Fetches synchronized and plain lyrics for the studio karaoke drawer.
        """
        if not title:
            return {"success": False, "error": "Title is required"}
        try:
            from lyrics_service import LyricsService
            lyrics = LyricsService.fetch_lyrics(title, artist, duration_sec)
            if lyrics:
                return {"success": True, "lyrics": lyrics}
            return {"success": False, "error": "No lyrics found"}
        except Exception as e:
            logger.error(f"Error fetching lyrics: {e}")
            return {"success": False, "error": str(e)}

    def scan_duplicates(self, tracks: List[Dict[str, Any]], folder: str) -> Dict[str, Any]:
        """
        Pre-scans the destination folder for duplicates before starting downloads.
        """
        if not isinstance(tracks, list):
            return {"success": False, "error": "Tracks parameter must be a list"}
        if not folder or not isinstance(folder, str) or not os.path.exists(folder):
            return {"success": False, "error": "Destination folder does not exist"}

        try:
            detector = DuplicateDetector(folder)
            duplicate_count = 0
            results = []

            for track in tracks:
                if not isinstance(track, dict):
                    continue
                dup = detector.check_duplicate(track.get("title", ""), track.get("artist", ""))
                track_copy = dict(track)
                if dup:
                    duplicate_count += 1
                    track_copy["duplicate_info"] = dup
                    track_copy["status"] = "duplicate"
                    track_copy["status_message"] = f"Duplicate: {dup['existing_file_name']}"
                else:
                    track_copy["duplicate_info"] = None
                    track_copy["status"] = "queued"
                    track_copy["status_message"] = "Ready"
                results.append(track_copy)

            return {
                "success": True,
                "duplicate_count": duplicate_count,
                "tracks": results
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def start_download(
        self,
        tracks: List[Dict[str, Any]],
        destination_folder: str,
        playlist_title: str = "Music Playlist",
        audio_quality: str = "192",
        filename_template: str = "title_artist",
        embed_lyrics: bool = True,
        save_lrc_file: bool = True,
        concurrency: int = 2
    ) -> Dict[str, Any]:
        """
        Starts the download queue worker with configurable concurrency in a background thread.
        """
        if self.current_worker and self.current_worker.stats.get("is_active"):
            return {"success": False, "error": "A download session is already active"}

        if not destination_folder or not isinstance(destination_folder, str):
            return {"success": False, "error": "Please choose a download folder"}

        if not tracks or not isinstance(tracks, list):
            return {"success": False, "error": "No tracks to download"}

        try:
            os.makedirs(destination_folder, exist_ok=True)
        except Exception as e:
            return {"success": False, "error": f"Cannot create download folder: {e}"}

        try:
            concurrency_val = int(concurrency)
        except (ValueError, TypeError):
            concurrency_val = 2
        concurrency_val = max(1, min(concurrency_val, 8))

        def on_progress(payload):
            self._send_event_to_frontend("download_progress", payload)

        def on_track_complete(payload):
            self._send_event_to_frontend("track_complete", payload)

        def on_duplicate_detected(track, dup_info):
            self._send_event_to_frontend("duplicate_detected", {
                "track": track,
                "duplicate_info": dup_info
            })

        def on_finished(stats):
            self._send_event_to_frontend("download_finished", stats)

        self.current_worker = DownloadWorker(
            tracks=tracks,
            destination_folder=destination_folder,
            playlist_title=playlist_title,
            audio_quality=audio_quality,
            filename_template=filename_template,
            embed_lyrics=embed_lyrics,
            save_lrc_file=save_lrc_file,
            max_concurrency=concurrency_val,
            on_progress=on_progress,
            on_track_complete=on_track_complete,
            on_duplicate_detected=on_duplicate_detected,
            on_finished=on_finished
        )

        self.worker_thread = threading.Thread(target=self.current_worker.run, daemon=True)
        self.worker_thread.start()

        return {"success": True, "message": "Download started"}

    def respond_duplicate(self, *args, **kwargs) -> Dict[str, Any]:
        """
        Handles duplicate confirmation response from user:
        Supports:
          respond_duplicate(decision: str, apply_to_all: bool = False)
          respond_duplicate(track_id: str, action: str, apply_to_all: bool = False)
        decision: 'skip' | 'download_again' | 'replace' | 'overwrite'
        """
        try:
            if not self.current_worker:
                return {"success": False, "error": "No active worker"}

            decision = "skip"
            apply_to_all = False

            if len(args) >= 3:
                # (track_id, action, apply_to_all)
                decision = str(args[1])
                apply_to_all = bool(args[2])
            elif len(args) == 2:
                decision = str(args[0])
                apply_to_all = bool(args[1])
            elif len(args) == 1:
                decision = str(args[0])

            if "action" in kwargs:
                decision = kwargs["action"]
            elif "decision" in kwargs:
                decision = kwargs["decision"]

            if "apply_to_all" in kwargs:
                apply_to_all = bool(kwargs["apply_to_all"])
            elif "applyToAll" in kwargs:
                apply_to_all = bool(kwargs["applyToAll"])

            if decision == "overwrite":
                decision = "replace"

            self.current_worker.provide_duplicate_decision(decision, apply_to_all)
            return {"success": True}
        except Exception as e:
            logger.error(f"Error responding to duplicate: {e}")
            return {"success": False, "error": str(e)}

    def pause_download(self) -> Dict[str, Any]:
        try:
            if self.current_worker:
                self.current_worker.pause()
                return {"success": True}
            return {"success": False, "error": "No active download"}
        except Exception as e:
            logger.error(f"Error pausing download: {e}")
            return {"success": False, "error": str(e)}

    def resume_download(self) -> Dict[str, Any]:
        try:
            if self.current_worker:
                self.current_worker.resume()
                return {"success": True}
            return {"success": False, "error": "No active download"}
        except Exception as e:
            logger.error(f"Error resuming download: {e}")
            return {"success": False, "error": str(e)}

    def cancel_download(self) -> Dict[str, Any]:
        try:
            if self.current_worker:
                self.current_worker.cancel()
                return {"success": True}
            return {"success": False, "error": "No active download"}
        except Exception as e:
            logger.error(f"Error cancelling download: {e}")
            return {"success": False, "error": str(e)}

    def minimize_to_tray(self) -> Dict[str, Any]:
        """Minimizes the window to the Windows Notification Area (System Tray)."""
        if self.window:
            try:
                self.window.hide()
                if self.tray_service:
                    self.tray_service.notify(
                        "BeatVault Minimized",
                        "BeatVault is running in background. Click tray icon or press media keys to control playback."
                    )
                return {"success": True}
            except Exception as e:
                logger.warning(f"Error minimizing window: {e}")
                return {"success": False, "error": str(e)}
        return {"success": False, "error": "No window reference"}

    def restore_from_tray(self) -> Dict[str, Any]:
        """Restores and shows the window from the system tray."""
        if self.window:
            try:
                self.window.show()
                self.window.restore()
                return {"success": True}
            except Exception as e:
                logger.warning(f"Error restoring window: {e}")
                return {"success": False, "error": str(e)}
        return {"success": False, "error": "No window reference"}

    def trigger_media_key(self, action: str):
        """Dispatches global media key action ('play_pause', 'next', 'prev') to the UI."""
        self._send_event_to_frontend("media_key_action", {"action": action})

    def get_status(self) -> Dict[str, Any]:
        if self.current_worker:
            return {"success": True, "stats": self.current_worker.stats}
        return {"success": False, "message": "Idle"}

    def _send_event_to_frontend(self, event_name: str, data: Any):
        """Dispatches event to Javascript inside the webview."""
        if self.window:
            try:
                json_data = json.dumps(data)
                js_code = f"window.handleBackendEvent && window.handleBackendEvent('{event_name}', {json_data});"
                self.window.evaluate_js(js_code)
            except Exception as e:
                logger.debug(f"Failed to evaluate js event {event_name}: {e}")

    def get_version_info(self) -> Dict[str, Any]:
        """Returns version and repository metadata."""
        return {"success": True, "info": get_version_info()}

    def check_for_updates(self, manual: bool = False) -> Dict[str, Any]:
        """Checks GitHub for application updates (non-blocking safe)."""
        try:
            return self.update_checker.check_for_updates(manual=manual)
        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
            return {
                "success": False,
                "update_available": False,
                "current_version": self.version,
                "latest_version": self.version,
                "error": str(e),
                "status_message": f"Error checking updates: {e}",
            }

    def open_release_page(self, url: Optional[str] = None) -> Dict[str, Any]:
        """Opens the GitHub release page or download URL in default browser."""
        try:
            success = open_release_page(url)
            return {"success": success}
        except Exception as e:
            logger.error(f"Error opening release page: {e}")
            return {"success": False, "error": str(e)}

    def download_update_asset(self, download_url: str) -> Dict[str, Any]:
        """Downloads the installer asset directly to user Downloads folder."""
        def progress_cb(current, total):
            pct = int((current / total) * 100) if total > 0 else 0
            self._send_event_to_frontend("update_download_progress", {
                "current": current,
                "total": total,
                "percent": pct,
            })

        try:
            res = download_release_asset(download_url, progress_callback=progress_cb)
            if res.get("success"):
                self._send_event_to_frontend("update_download_complete", res)
            return res
        except Exception as e:
            return {"success": False, "error": str(e)}

    def start_background_update_check(self, delay_seconds: float = 2.5):
        """Runs background check at startup; dispatches 'update_available' if newer release exists."""
        def on_checked(result: Dict[str, Any]):
            if result.get("update_available"):
                logger.info(f"Update available: {result.get('latest_version')}. Sending to UI...")
                self._send_event_to_frontend("update_available", result)

        return self.update_checker.check_for_updates_async(
            callback=on_checked,
            manual=False,
            delay_seconds=delay_seconds,
        )

    # =========================================================================
    # High-level API Bridge Compatibility Aliases
    # =========================================================================
    def get_playlist(self, url: str) -> Dict[str, Any]:
        """Alias for load_playlist."""
        return self.load_playlist(url)

    def download_playlist(self, tracks: List[Dict[str, Any]], destination_folder: str = "", **kwargs) -> Dict[str, Any]:
        """Alias for start_download."""
        return self.start_download(tracks, destination_folder, **kwargs)

    def download_track(self, track: Dict[str, Any], destination_folder: str = "", **kwargs) -> Dict[str, Any]:
        """Alias for downloading single track."""
        return self.start_download([track], destination_folder, **kwargs)

    def open_download_folder(self, folder_path: str = "") -> Dict[str, Any]:
        """Alias for open_folder."""
        return self.open_folder(folder_path)

    def get_downloads(self) -> Dict[str, Any]:
        """Alias returning active downloads/status."""
        return self.get_status()


# Module-level alias
BeatVaultApi = AppAPI



