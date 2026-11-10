import os
import sys
import time
import shutil
import logging
import threading
import tempfile
import concurrent.futures
from typing import Dict, Any, List, Optional, Callable
import requests
import static_ffmpeg

# Ensure static ffmpeg binaries are added to PATH
try:
    static_ffmpeg.add_paths()
except Exception as e:
    logging.warning(f"Failed to add static_ffmpeg paths: {e}")

import yt_dlp
import mutagen
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC, COMM

from duplicate_detector import DuplicateDetector
from lyrics_service import LyricsService

logger = logging.getLogger("downloader")

class DownloadWorker:
    def __init__(
        self,
        tracks: List[Dict[str, Any]],
        destination_folder: str,
        playlist_title: str = "Spotify Playlist",
        audio_quality: str = "192",
        filename_template: str = "title_artist",
        embed_lyrics: bool = True,
        save_lrc_file: bool = True,
        max_concurrency: int = 2,
        on_progress: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_track_complete: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_duplicate_detected: Optional[Callable[[Dict[str, Any], Dict[str, Any]], None]] = None,
        on_finished: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        self.tracks = tracks
        self.destination_folder = destination_folder
        self.playlist_title = playlist_title
        self.audio_quality = audio_quality  # "192" or "320"
        self.filename_template = filename_template  # "title_artist", "artist_title", "track_title_artist", "title_only"
        self.embed_lyrics = embed_lyrics
        self.save_lrc_file = save_lrc_file
        self.max_concurrency = max_concurrency  # strictly 2 as requested

        self.on_progress = on_progress
        self.on_track_complete = on_track_complete
        self.on_duplicate_detected = on_duplicate_detected
        self.on_finished = on_finished

        self.detector = DuplicateDetector(destination_folder)
        
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()

        # Thread synchronization locks
        self._stats_lock = threading.Lock()
        self._detector_lock = threading.Lock()
        self._duplicate_prompt_lock = threading.Lock()
        
        self._duplicate_response_event = threading.Event()
        self._duplicate_decision = None
        self._apply_to_all_duplicates = False
        self._remembered_duplicate_decision = None

        self.stats = {
            "total": len(tracks),
            "completed": 0,
            "skipped": 0,
            "failed": 0,
            "duplicates": 0,
            "is_active": False,
            "is_paused": False,
            "is_cancelled": False,
            "active_tracks": []
        }

    def cancel(self):
        """Signals the worker to stop processing remaining tracks."""
        self._stop_event.set()
        self._pause_event.set()
        self._duplicate_response_event.set()
        with self._stats_lock:
            self.stats["is_cancelled"] = True

    def pause(self):
        """Pauses downloading."""
        self._pause_event.clear()
        with self._stats_lock:
            self.stats["is_paused"] = True

    def resume(self):
        """Resumes downloading."""
        self._pause_event.set()
        with self._stats_lock:
            self.stats["is_paused"] = False

    def provide_duplicate_decision(self, decision: str, apply_to_all: bool = False):
        """
        Called by the UI when the user chooses how to handle a duplicate:
        decision: 'skip' | 'download_again' | 'replace'
        """
        self._duplicate_decision = decision
        if apply_to_all:
            self._apply_to_all_duplicates = True
            self._remembered_duplicate_decision = decision
        self._duplicate_response_event.set()

    def run(self):
        """Main execution entry using a thread pool with concurrency = 2."""
        with self._stats_lock:
            self.stats["is_active"] = True

        os.makedirs(self.destination_folder, exist_ok=True)
        with self._detector_lock:
            self.detector.refresh_cache()

        logger.info(f"Starting download queue with {len(self.tracks)} tracks (Concurrency: {self.max_concurrency})")

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_concurrency) as executor:
            futures = [executor.submit(self._process_single_track, track) for track in self.tracks]
            concurrent.futures.wait(futures)

        with self._stats_lock:
            self.stats["is_active"] = False
            self.stats["active_tracks"] = []

        if self.on_finished:
            self.on_finished(self.stats)

    def _process_single_track(self, track: Dict[str, Any]):
        """Processes a single track through duplicate check, download, conversion, and metadata."""
        if self._stop_event.is_set():
            track["status"] = "cancelled"
            track["status_message"] = "Cancelled"
            return

        self._pause_event.wait()
        if self._stop_event.is_set():
            return

        track_title = track.get("title", "Unknown Title")
        track_artist = track.get("artist", "Unknown Artist")
        track_index = track.get("index", 1)

        with self._stats_lock:
            if track not in self.stats["active_tracks"]:
                self.stats["active_tracks"].append(track)

        # Step 1: Duplicate Detection
        track["status"] = "checking"
        track["status_message"] = "Checking for duplicates..."
        self._emit_progress(track, 5)

        with self._detector_lock:
            dup_info = self.detector.check_duplicate(track_title, track_artist)

        allow_copy = False
        allow_overwrite = False

        if dup_info:
            with self._stats_lock:
                self.stats["duplicates"] += 1
            track["duplicate_info"] = dup_info

            decision = None
            if self._apply_to_all_duplicates and self._remembered_duplicate_decision:
                decision = self._remembered_duplicate_decision
            else:
                # Synchronize duplicate prompt so only 1 modal prompts user at a time
                with self._duplicate_prompt_lock:
                    if self._stop_event.is_set():
                        return
                    if self._apply_to_all_duplicates and self._remembered_duplicate_decision:
                        decision = self._remembered_duplicate_decision
                    else:
                        track["status"] = "duplicate_prompt"
                        track["status_message"] = "Duplicate detected. Awaiting decision..."
                        self._duplicate_response_event.clear()

                        if self.on_duplicate_detected:
                            self.on_duplicate_detected(track, dup_info)

                        self._duplicate_response_event.wait()
                        if self._stop_event.is_set():
                            return
                        decision = self._duplicate_decision

            logger.info(f"Duplicate decision for '{track_title}': {decision}")

            if decision == "skip":
                track["status"] = "skipped"
                track["status_message"] = "Skipped (Duplicate already exists)"
                with self._stats_lock:
                    self.stats["skipped"] += 1
                    if track in self.stats["active_tracks"]:
                        self.stats["active_tracks"].remove(track)
                self._emit_track_complete(track)
                return
            elif decision == "download_again":
                allow_copy = True
            elif decision == "replace":
                allow_overwrite = True
            else:
                track["status"] = "skipped"
                track["status_message"] = "Skipped"
                with self._stats_lock:
                    self.stats["skipped"] += 1
                    if track in self.stats["active_tracks"]:
                        self.stats["active_tracks"].remove(track)
                self._emit_track_complete(track)
                return

        # Step 2: Determine Safe Output Path (Song Name first)
        with self._detector_lock:
            if allow_overwrite and dup_info:
                target_path = dup_info["existing_file_path"]
            else:
                target_path, _ = self.detector.get_destination_filename(
                    track_title,
                    track_artist,
                    track_index=track_index,
                    template=self.filename_template,
                    allow_copy=allow_copy
                )

        track["destination_file"] = target_path

        # Step 3: Download, Convert & Tag
        track["status"] = "downloading"
        track["status_message"] = "Searching authorized source..."
        self._emit_progress(track, 15)

        success = self._download_and_convert(track, target_path)

        with self._stats_lock:
            if track in self.stats["active_tracks"]:
                self.stats["active_tracks"].remove(track)

            if success:
                track["status"] = "completed"
                track["status_message"] = "Saved to folder"
                track["progress"] = 100
                self.stats["completed"] += 1
            else:
                track["status"] = "failed"
                track["status_message"] = track.get("error_message", "Download failed")
                self.stats["failed"] += 1

        with self._detector_lock:
            self.detector.refresh_cache()

        self._emit_track_complete(track)

    def _emit_progress(self, track: Dict[str, Any], percent: float, speed_str: str = "", eta_str: str = ""):
        track["progress"] = round(percent, 1)
        if self.on_progress:
            self.on_progress({
                "track": track,
                "stats": self.stats,
                "percent": percent,
                "speed": speed_str,
                "eta": eta_str
            })

    def _emit_track_complete(self, track: Dict[str, Any]):
        if self.on_track_complete:
            self.on_track_complete({
                "track": track,
                "stats": self.stats
            })

    def _smart_find_source(self, track: Dict[str, Any]) -> str:
        """
        Smart duration matching: searches top candidates, compares duration against Spotify duration.
        GUARANTEE: If no candidate matches duration, it immediately falls back to candidate #1 so
        no song ever fails to download because of duration matching!
        """
        # Direct source URL from YouTube, SoundCloud, etc.
        if track.get("direct_source_url"):
            return track["direct_source_url"]
        title = track.get("title", "")
        artist = track.get("artist", "")
        target_duration = (track.get("duration_ms", 0) or 0) / 1000.0

        fallback_query = f"ytsearch1:{artist} - {title} audio".strip()

        # If track duration not provided, use standard search
        if target_duration < 15:
            return fallback_query

        search_query = f"ytsearch5:{artist} - {title} audio".strip()
        ydl_opts = {
            "extract_flat": True,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(search_query, download=False)
                entries = info.get("entries", []) if info else []

                if not entries:
                    return fallback_query

                title_lower = title.lower()
                unwanted_tags = ["live", "concert", "slowed", "reverb", "8d", "reaction"]
                # Only filter unwanted tags if the song title doesn't legitimately have them
                active_filter = [w for w in unwanted_tags if w not in title_lower]

                best_url = None
                smallest_diff = float("inf")

                for entry in entries:
                    if not entry:
                        continue
                    cand_title = (entry.get("title") or "").lower()
                    cand_dur = entry.get("duration") or 0

                    if any(w in cand_title for w in active_filter):
                        continue

                    if cand_dur > 0:
                        diff = abs(cand_dur - target_duration)
                        if diff <= 12 and diff < smallest_diff:
                            smallest_diff = diff
                            best_url = entry.get("url") or (f"https://www.youtube.com/watch?v={entry.get('id')}" if entry.get("id") else None)

                if best_url:
                    logger.info(f"Smart duration matched for '{title}' (diff: {smallest_diff:.1f}s)")
                    return best_url

        except Exception as e:
            logger.debug(f"Smart duration match note: {e}")

        # Rock-solid fallback: returns search query
        return fallback_query

    def _download_and_convert(self, track: Dict[str, Any], final_output_path: str) -> bool:
        """
        Downloads audio using yt-dlp, extracts to MP3 via static ffmpeg,
        embeds song's original artwork & lyrics.
        """
        title = track.get("title", "")
        artist = track.get("artist", "")
        target_duration = (track.get("duration_ms", 0) or 0) / 1000.0

        # Smart source query
        query = self._smart_find_source(track)

        temp_dir = tempfile.mkdtemp(prefix="spot_dl_")
        temp_out_tmpl = os.path.join(temp_dir, "temp_audio.%(ext)s")

        def ytdl_progress_hook(d):
            if self._stop_event.is_set():
                raise Exception("Download cancelled by user")

            status = d.get("status")
            if status == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes", 0)
                speed = d.get("speed") or 0
                eta = d.get("eta") or 0

                percent = (downloaded / total * 70.0) if total > 0 else 30.0
                speed_str = f"{speed / (1024 * 1024):.1f} MB/s" if speed > 1024 * 1024 else f"{speed / 1024:.0f} KB/s"
                eta_str = f"{int(eta)}s" if eta else ""

                track["status"] = "downloading"
                track["status_message"] = f"Downloading ({speed_str})"
                self._emit_progress(track, 20.0 + percent, speed_str, eta_str)

            elif status == "finished":
                track["status"] = "converting"
                track["status_message"] = "Converting audio to MP3..."
                self._emit_progress(track, 85.0)

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": temp_out_tmpl,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": self.audio_quality,
            }],
            "progress_hooks": [ytdl_progress_hook],
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "noplaylist": True,
        }

        try:
            yt_thumbnail = None
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(query, download=True)
                if not info:
                    track["error_message"] = "No authorized audio source found"
                    return False
                entry = info.get("entries", [info])[0] if "entries" in info else info
                yt_thumbnail = entry.get("thumbnail")
                if not yt_thumbnail and entry.get("thumbnails"):
                    yt_thumbnail = entry["thumbnails"][-1].get("url")

            # Locate the generated mp3 file in temp_dir
            generated_mp3 = None
            for f in os.listdir(temp_dir):
                if f.lower().endswith(".mp3"):
                    generated_mp3 = os.path.join(temp_dir, f)
                    break

            if not generated_mp3 or not os.path.exists(generated_mp3):
                track["error_message"] = "MP3 conversion failed"
                return False

            # Embed ID3 Tags (Title, Artist, Album, Song's Original Cover Art)
            track["status_message"] = "Writing MP3 ID3 metadata & original cover..."
            self._embed_id3_tags(generated_mp3, track, yt_thumbnail=yt_thumbnail)

            # Move to final destination
            if os.path.exists(final_output_path):
                try:
                    os.remove(final_output_path)
                except Exception:
                    pass

            shutil.move(generated_mp3, final_output_path)

            # Embed Lyrics & save .lrc file if enabled
            if self.embed_lyrics:
                track["status_message"] = "Fetching & embedding lyrics..."
                try:
                    LyricsService.embed_lyrics_to_mp3(
                        final_output_path,
                        title,
                        artist,
                        duration_sec=int(target_duration) if target_duration > 0 else None,
                        save_lrc_file=self.save_lrc_file
                    )
                except Exception as lyr_err:
                    logger.debug(f"Lyrics embedding skipped: {lyr_err}")

            return True

        except Exception as e:
            logger.error(f"Error downloading track {title}: {e}")
            track["error_message"] = str(e)
            return False

        finally:
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass

    def _embed_id3_tags(self, mp3_path: str, track: Dict[str, Any], yt_thumbnail: Optional[str] = None):
        """Embeds ID3v2.3 tags and the song's original artwork into the MP3."""
        try:
            audio = MP3(mp3_path, ID3=ID3)
            try:
                audio.add_tags()
            except Exception:
                pass

            title = track.get("title", "")
            artist = track.get("artist", "")
            album = self.playlist_title or "Spotify Playlist"

            if title:
                audio.tags.add(TIT2(encoding=3, text=title))
            if artist:
                audio.tags.add(TPE1(encoding=3, text=artist))
            if album:
                audio.tags.add(TALB(encoding=3, text=album))

            audio.tags.add(COMM(encoding=3, lang="eng", desc="Source", text="Downloaded via BeatVault"))

            # Resolve the song's original cover URL
            cover_url = ""
            track_uri = track.get("uri") or track.get("id") or ""
            if "track:" in str(track_uri):
                track_id = str(track_uri).split(":")[-1]
                try:
                    oembed_resp = requests.get(
                        f"https://open.spotify.com/oembed?url=https://open.spotify.com/track/{track_id}",
                        timeout=5
                    )
                    if oembed_resp.status_code == 200:
                        cover_url = oembed_resp.json().get("thumbnail_url", "")
                except Exception as oe_err:
                    logger.debug(f"Could not fetch Spotify track oembed cover: {oe_err}")

            if not cover_url and yt_thumbnail:
                cover_url = yt_thumbnail

            if not cover_url:
                cover_url = track.get("cover_url", "")

            if cover_url:
                try:
                    img_resp = requests.get(cover_url, timeout=10)
                    if img_resp.status_code == 200:
                        mime_type = "image/jpeg"
                        if "png" in cover_url.lower():
                            mime_type = "image/png"
                        elif "webp" in cover_url.lower():
                            mime_type = "image/webp"

                        audio.tags.add(
                            APIC(
                                encoding=3,
                                mime=mime_type,
                                type=3,  # Front Cover
                                desc="Front Cover",
                                data=img_resp.content
                            )
                        )
                except Exception as img_err:
                    logger.warning(f"Could not download song cover art: {img_err}")

            audio.save(v2_version=3)
        except Exception as e:
            logger.warning(f"Failed to embed ID3 tags: {e}")
