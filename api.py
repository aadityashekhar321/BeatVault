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

logger = logging.getLogger("api")

class AppAPI:
    def __init__(self, window=None):
        self.window = window
        self.platform_service = PlatformService()
        self.current_worker: Optional[DownloadWorker] = None
        self.worker_thread: Optional[threading.Thread] = None
        self.tray_service = None

    def set_window(self, window):
        self.window = window

    def set_tray_service(self, tray_service):
        self.tray_service = tray_service

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
        try:
            data = self.platform_service.fetch_metadata(url)
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
        Reads a local MP3 file and returns base64 audio data for the in-app player.
        """
        if not file_path or not os.path.exists(file_path):
            return {"success": False, "error": "File not found"}

        try:
            with open(file_path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("utf-8")
            data_uri = f"data:audio/mp3;base64,{encoded}"
            return {"success": True, "data_url": data_uri}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def scan_duplicates(self, tracks: List[Dict[str, Any]], folder: str) -> Dict[str, Any]:
        """
        Pre-scans the destination folder for duplicates before starting downloads.
        """
        if not folder or not os.path.exists(folder):
            return {"success": False, "error": "Destination folder does not exist"}

        try:
            detector = DuplicateDetector(folder)
            duplicate_count = 0
            results = []

            for track in tracks:
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
        save_lrc_file: bool = True
    ) -> Dict[str, Any]:
        """
        Starts the download queue worker with concurrency = 2 in a background thread.
        """
        if self.current_worker and self.current_worker.stats.get("is_active"):
            return {"success": False, "error": "A download session is already active"}

        if not destination_folder:
            return {"success": False, "error": "Please choose a download folder"}

        if not tracks:
            return {"success": False, "error": "No tracks to download"}

        os.makedirs(destination_folder, exist_ok=True)

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
            max_concurrency=2,  # Exactly 2 parallel downloads
            on_progress=on_progress,
            on_track_complete=on_track_complete,
            on_duplicate_detected=on_duplicate_detected,
            on_finished=on_finished
        )

        self.worker_thread = threading.Thread(target=self.current_worker.run, daemon=True)
        self.worker_thread.start()

        return {"success": True, "message": "Download started"}

    def respond_duplicate(self, decision: str, apply_to_all: bool = False) -> Dict[str, Any]:
        """
        Handles duplicate confirmation response from user:
        decision: 'skip' | 'download_again' | 'replace'
        """
        if not self.current_worker:
            return {"success": False, "error": "No active worker"}

        self.current_worker.provide_duplicate_decision(decision, apply_to_all)
        return {"success": True}

    def pause_download(self) -> Dict[str, Any]:
        if self.current_worker:
            self.current_worker.pause()
            return {"success": True}
        return {"success": False, "error": "No active download"}

    def resume_download(self) -> Dict[str, Any]:
        if self.current_worker:
            self.current_worker.resume()
            return {"success": True}
        return {"success": False, "error": "No active download"}

    def cancel_download(self) -> Dict[str, Any]:
        if self.current_worker:
            self.current_worker.cancel()
            return {"success": True}
        return {"success": False, "error": "No active download"}

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
