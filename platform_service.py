import os
import re
import json
import logging
from typing import Dict, Any, List, Optional
import requests
import yt_dlp

from spotify_service import SpotifyService

logger = logging.getLogger("platform_service")

class PlatformService:
    def __init__(self):
        self.spotify_service = SpotifyService()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        })

    def detect_platform(self, url: str) -> str:
        """
        Detects platform from URL:
        'spotify' | 'youtube' | 'apple_music' | 'soundcloud' | 'unknown'
        """
        if not url or not isinstance(url, str):
            return "unknown"
        url = url.strip().lower()

        if "spotify.com" in url or url.startswith("spotify:"):
            return "spotify"
        elif "youtube.com" in url or "youtu.be" in url:
            return "youtube"
        elif "music.apple.com" in url or "itunes.apple.com" in url:
            return "apple_music"
        elif "soundcloud.com" in url:
            return "soundcloud"
        return "unknown"

    def fetch_metadata(self, url: str) -> Dict[str, Any]:
        """
        Unified router that dispatches URL to the corresponding platform scraper.
        """
        if not url or not url.strip():
            raise ValueError("URL cannot be empty")

        url = url.strip()
        platform = self.detect_platform(url)

        if platform == "spotify":
            data = self.spotify_service.fetch_playlist_metadata(url)
            data["platform"] = "spotify"
            data["platform_name"] = "Spotify"
            data["platform_badge"] = "🟢 Spotify"
            for t in data.get("tracks", []):
                t["platform"] = "spotify"
                t["direct_source_url"] = None
            return data

        elif platform == "youtube":
            return self._fetch_youtube_metadata(url)

        elif platform == "apple_music":
            return self._fetch_apple_music_metadata(url)

        elif platform == "soundcloud":
            return self._fetch_soundcloud_metadata(url)

        else:
            # Fallback: try yt_dlp generic extraction
            try:
                return self._fetch_youtube_metadata(url)
            except Exception:
                raise ValueError("Unsupported or invalid link. Please provide a Spotify, YouTube, Apple Music, or SoundCloud link.")

    def _fetch_youtube_metadata(self, url: str) -> Dict[str, Any]:
        """Extracts metadata from YouTube or YouTube Music playlist / video."""
        logger.info(f"Extracting YouTube metadata for: {url}")
        ydl_opts = {
            "extract_flat": "in_playlist",
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                raise ValueError("Could not retrieve YouTube content from this link.")

        is_playlist = "entries" in info
        title = info.get("title", "YouTube Music")
        owner = info.get("uploader") or info.get("channel") or "YouTube"
        cover_url = ""
        thumbnails = info.get("thumbnails", [])
        if thumbnails:
            cover_url = thumbnails[-1].get("url", "")

        tracks = []
        if is_playlist:
            raw_entries = info.get("entries") or []
            for idx, entry in enumerate(raw_entries):
                if not entry:
                    continue
                t_title = entry.get("title", "Unknown Title")
                t_artist = entry.get("uploader") or entry.get("channel") or owner

                # Clean common YouTube artist - title format (e.g. "Artist - Song (Official Video)")
                clean_title, clean_artist = self._clean_youtube_title(t_title, t_artist)

                dur_sec = entry.get("duration") or 0
                dur_ms = int(dur_sec * 1000)
                dur_fmt = f"{int(dur_sec) // 60}:{int(dur_sec) % 60:02d}" if dur_sec > 0 else "0:00"

                t_thumb = ""
                e_thumbs = entry.get("thumbnails", [])
                if e_thumbs:
                    t_thumb = e_thumbs[-1].get("url", "")
                elif cover_url:
                    t_thumb = cover_url

                video_id = entry.get("id") or str(idx + 1)
                direct_url = entry.get("url") or f"https://www.youtube.com/watch?v={video_id}"
                if not direct_url.startswith("http"):
                    direct_url = f"https://www.youtube.com/watch?v={direct_url}"

                tracks.append({
                    "index": idx + 1,
                    "id": f"yt_{video_id}",
                    "title": clean_title,
                    "artist": clean_artist,
                    "album": title,
                    "duration_ms": dur_ms,
                    "duration_formatted": dur_fmt,
                    "cover_url": t_thumb,
                    "audio_preview": None,
                    "direct_source_url": direct_url,
                    "platform": "youtube",
                    "status": "queued",
                    "status_message": "Ready",
                    "progress": 0,
                    "selected": True,
                    "duplicate_info": None
                })
        else:
            # Single YouTube Video
            t_title = info.get("title", "YouTube Track")
            t_artist = info.get("uploader") or info.get("channel") or "Unknown Artist"
            clean_title, clean_artist = self._clean_youtube_title(t_title, t_artist)
            dur_sec = info.get("duration") or 0
            dur_ms = int(dur_sec * 1000)
            dur_fmt = f"{int(dur_sec) // 60}:{int(dur_sec) % 60:02d}" if dur_sec > 0 else "0:00"

            tracks.append({
                "index": 1,
                "id": f"yt_{info.get('id', '1')}",
                "title": clean_title,
                "artist": clean_artist,
                "album": "Single",
                "duration_ms": dur_ms,
                "duration_formatted": dur_fmt,
                "cover_url": cover_url,
                "audio_preview": None,
                "direct_source_url": info.get("webpage_url") or url,
                "platform": "youtube",
                "status": "queued",
                "status_message": "Ready",
                "progress": 0,
                "selected": True,
                "duplicate_info": None
            })

        is_yt_music = "music.youtube.com" in url
        badge = "🔴 YouTube Music" if is_yt_music else "🔴 YouTube"
        return {
            "platform": "youtube",
            "platform_name": "YouTube Music" if is_yt_music else "YouTube",
            "platform_badge": badge,
            "title": title,
            "owner": owner,
            "track_count": len(tracks),
            "cover_url": cover_url,
            "tracks": tracks
        }

    def _fetch_apple_music_metadata(self, url: str) -> Dict[str, Any]:
        """Extracts metadata from Apple Music playlist, album, or single track via embedded JSON-LD."""
        logger.info(f"Extracting Apple Music metadata for: {url}")
        resp = self.session.get(url, timeout=10)
        if resp.status_code != 200:
            raise ValueError(f"Apple Music returned HTTP {resp.status_code}")

        pattern = r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
        matches = re.findall(pattern, resp.text, re.DOTALL)
        if not matches:
            raise ValueError("Could not parse Apple Music page structure.")

        collection_data = None
        single_track_data = None

        for m in matches:
            try:
                parsed = json.loads(m.strip())
                mtype = parsed.get("@type")
                if mtype in ["MusicAlbum", "MusicPlaylist"]:
                    collection_data = parsed
                    break
                elif mtype in ["MusicRecording", "MusicComposition"]:
                    single_track_data = parsed
                    break
            except Exception:
                continue

        if not collection_data and not single_track_data:
            raise ValueError("No playlist, album, or song metadata found on this Apple Music page.")

        if collection_data:
            title = collection_data.get("name", "Apple Music Collection")
            by_artist = collection_data.get("byArtist", [])
            if isinstance(by_artist, list) and len(by_artist) > 0:
                owner = by_artist[0].get("name", "Apple Music")
            elif isinstance(by_artist, dict):
                owner = by_artist.get("name", "Apple Music")
            else:
                owner = str(by_artist) if by_artist else "Apple Music"

            raw_tracks = collection_data.get("tracks") or collection_data.get("track") or []
            cover_url = ""

            # Check if there is trackLockup rich data in the page for playlists
            lockup_map = {}
            for s in re.findall(r'<script[^>]*>(.*?)</script>', resp.text, re.DOTALL):
                if 'trackLockup' in s:
                    try:
                        raw_json = json.loads(s.strip())
                        def extract_items(obj):
                            if isinstance(obj, dict):
                                if obj.get('itemKind') == 'trackLockup':
                                    return obj.get('items', [])
                                for v in obj.values():
                                    res = extract_items(v)
                                    if res: return res
                            elif isinstance(obj, list):
                                for v in obj:
                                    res = extract_items(v)
                                    if res: return res
                            return None
                        items = extract_items(raw_json)
                        if items:
                            for it in items:
                                t_title = it.get('title')
                                t_artist = it.get('artistName')
                                if t_title and t_artist:
                                    lockup_map[t_title.lower().strip()] = t_artist
                    except Exception:
                        pass

            tracks = []
            for idx, item in enumerate(raw_tracks):
                t_name = item.get("name", "Unknown Title")
                audio_info = item.get("audio", {}) if isinstance(item.get("audio"), dict) else {}
                dur_str = item.get("duration") or audio_info.get("duration") or "PT0S"
                dur_sec = self._parse_iso8601_duration(dur_str)
                dur_ms = dur_sec * 1000
                dur_fmt = f"{dur_sec // 60}:{dur_sec % 60:02d}" if dur_sec > 0 else "0:00"

                t_cover = audio_info.get("thumbnailUrl", "")
                if not cover_url and t_cover:
                    cover_url = t_cover

                preview_url = audio_info.get("contentUrl", "")
                t_artist = lockup_map.get(t_name.lower().strip()) or owner

                tracks.append({
                    "index": idx + 1,
                    "id": f"apple_{idx + 1}",
                    "title": t_name,
                    "artist": t_artist,
                    "album": title,
                    "duration_ms": dur_ms,
                    "duration_formatted": dur_fmt,
                    "cover_url": t_cover or cover_url,
                    "audio_preview": preview_url,
                    "direct_source_url": None,  # Apple Music audio is protected; will use duration matcher
                    "platform": "apple_music",
                    "status": "queued",
                    "status_message": "Ready",
                    "progress": 0,
                    "selected": True,
                    "duplicate_info": None
                })

            return {
                "platform": "apple_music",
                "platform_name": "Apple Music",
                "platform_badge": "🍎 Apple Music",
                "title": title,
                "owner": owner,
                "track_count": len(tracks),
                "cover_url": cover_url,
                "tracks": tracks
            }
        else:
            # Single Track
            title = single_track_data.get("name", "Apple Music Track")
            audio_sub = single_track_data.get("audio", {})
            if not isinstance(audio_sub, dict):
                audio_sub = {}

            by_artist = single_track_data.get("byArtist") or audio_sub.get("byArtist")
            artist = "Unknown Artist"
            if isinstance(by_artist, list) and len(by_artist) > 0:
                artist = by_artist[0].get("name", "Unknown Artist")
            elif isinstance(by_artist, dict):
                artist = by_artist.get("name", "Unknown Artist")

            album = "Single"
            in_album = audio_sub.get("inAlbum")
            if isinstance(in_album, dict) and in_album.get("name"):
                album = in_album.get("name")

            dur_str = single_track_data.get("timeRequired") or single_track_data.get("duration") or audio_sub.get("duration") or "PT0S"
            dur_sec = self._parse_iso8601_duration(dur_str)
            dur_ms = dur_sec * 1000
            dur_fmt = f"{dur_sec // 60}:{dur_sec % 60:02d}" if dur_sec > 0 else "0:00"

            cover_url = single_track_data.get("image") or audio_sub.get("image") or audio_sub.get("thumbnailUrl") or ""
            preview_url = audio_sub.get("contentUrl", "")

            track = {
                "index": 1,
                "id": "apple_1",
                "title": title,
                "artist": artist,
                "album": album,
                "duration_ms": dur_ms,
                "duration_formatted": dur_fmt,
                "cover_url": cover_url,
                "audio_preview": preview_url,
                "direct_source_url": None,
                "platform": "apple_music",
                "status": "queued",
                "status_message": "Ready",
                "progress": 0,
                "selected": True,
                "duplicate_info": None
            }

            return {
                "platform": "apple_music",
                "platform_name": "Apple Music",
                "platform_badge": "🍎 Apple Music",
                "title": title,
                "owner": artist,
                "track_count": 1,
                "cover_url": cover_url,
                "tracks": [track]
            }

    def _fetch_soundcloud_metadata(self, url: str) -> Dict[str, Any]:
        """Extracts metadata from SoundCloud playlist/set or track via yt-dlp."""
        logger.info(f"Extracting SoundCloud metadata for: {url}")
        ydl_opts = {
            "extract_flat": "in_playlist",
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                raise ValueError("Could not extract SoundCloud content from this link.")

        title = info.get("title", "SoundCloud Playlist")
        owner = info.get("uploader") or "SoundCloud"
        cover_url = info.get("thumbnail", "")

        is_playlist = "entries" in info
        tracks = []

        if is_playlist:
            raw_entries = info.get("entries") or []
            for idx, entry in enumerate(raw_entries):
                if not entry:
                    continue
                t_title = entry.get("title", "Unknown Track")
                t_artist = entry.get("uploader") or owner
                dur_sec = entry.get("duration") or 0
                dur_ms = int(dur_sec * 1000)
                dur_fmt = f"{int(dur_sec) // 60}:{int(dur_sec) % 60:02d}" if dur_sec > 0 else "0:00"
                t_thumb = entry.get("thumbnail") or cover_url

                tracks.append({
                    "index": idx + 1,
                    "id": f"sc_{entry.get('id', idx + 1)}",
                    "title": t_title,
                    "artist": t_artist,
                    "album": title,
                    "duration_ms": dur_ms,
                    "duration_formatted": dur_fmt,
                    "cover_url": t_thumb,
                    "audio_preview": None,
                    "direct_source_url": entry.get("url") or entry.get("webpage_url"),
                    "platform": "soundcloud",
                    "status": "queued",
                    "status_message": "Ready",
                    "progress": 0,
                    "selected": True,
                    "duplicate_info": None
                })
        else:
            dur_sec = info.get("duration") or 0
            dur_ms = int(dur_sec * 1000)
            dur_fmt = f"{int(dur_sec) // 60}:{int(dur_sec) % 60:02d}" if dur_sec > 0 else "0:00"

            tracks.append({
                "index": 1,
                "id": f"sc_{info.get('id', '1')}",
                "title": title,
                "artist": owner,
                "album": "Single",
                "duration_ms": dur_ms,
                "duration_formatted": dur_fmt,
                "cover_url": cover_url,
                "audio_preview": None,
                "direct_source_url": info.get("webpage_url") or url,
                "platform": "soundcloud",
                "status": "queued",
                "status_message": "Ready",
                "progress": 0,
                "selected": True,
                "duplicate_info": None
            })

        return {
            "platform": "soundcloud",
            "platform_name": "SoundCloud",
            "platform_badge": "🟠 SoundCloud",
            "title": title,
            "owner": owner,
            "track_count": len(tracks),
            "cover_url": cover_url,
            "tracks": tracks
        }

    @staticmethod
    def _clean_youtube_title(title: str, default_artist: str) -> tuple[str, str]:
        """
        Cleans common YouTube video titles like:
        'The Weeknd - Blinding Lights (Official Video)' -> ('Blinding Lights', 'The Weeknd')
        """
        if not title:
            return ("Unknown Title", default_artist)

        # Remove parenthetical tags like (Official Video), [Audio], (Lyrics), etc.
        cleaned = re.sub(r"[\(\[\{]\s*(?:official\s*(?:video|audio|music\s*video|lyric\s*video|visualizer)|lyrics?|hd|4k|audio)\s*[\)\]\}]", "", title, flags=re.IGNORECASE).strip()

        # Check for "Artist - Title" separator
        if " - " in cleaned:
            parts = cleaned.split(" - ", 1)
            artist_part = parts[0].strip()
            title_part = parts[1].strip()
            if artist_part and title_part:
                return (title_part, artist_part)

        return (cleaned or title, default_artist)

    @staticmethod
    def _parse_iso8601_duration(dur_str: str) -> int:
        """
        Parses ISO 8601 duration format (e.g. 'PT3M45S' or 'PT33S') to total seconds.
        """
        if not dur_str:
            return 0
        match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", dur_str)
        if not match:
            return 0
        h = int(match.group(1) or 0)
        m = int(match.group(2) or 0)
        s = int(match.group(3) or 0)
        return (h * 3600) + (m * 60) + s
