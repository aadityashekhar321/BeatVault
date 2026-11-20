import os
import re
import logging
from typing import Dict, Any, Optional, List, Tuple
import requests
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, USLT, TXXX

logger = logging.getLogger("lyrics_service")

class LyricsService:
    BASE_URL = "https://lrclib.net/api"

    @staticmethod
    def clean_text(text: str) -> str:
        """Strips parentheticals and extra tags for better lyric search hits."""
        if not text:
            return ""
        # Remove (feat. ...), [official audio], etc.
        cleaned = re.sub(r"[\(\[\{].*?[\)\]\}]", "", text)
        return cleaned.strip()

    @staticmethod
    def parse_timecode(tag: str) -> Optional[float]:
        """
        Parses [mm:ss.xx] or [mm:ss.xxx] or mm:ss.xx into total seconds as a float.
        Returns None if format does not match.
        """
        if not tag or not isinstance(tag, str):
            return None
        match = re.search(r"\[?(\d{2}):(\d{2})(?:\.(\d{2,3}))?\]?", tag)
        if not match:
            return None
        mins = int(match.group(1))
        secs = int(match.group(2))
        ms_str = match.group(3) or "0"
        ms_val = int(ms_str.ljust(3, "0")[:3])
        return round(mins * 60 + secs + (ms_val / 1000.0), 3)

    @classmethod
    def parse_lrc(cls, lrc_text: str) -> List[Dict[str, Any]]:
        """
        Parses LRC synced lyrics text into structured entries:
        [{'time': float, 'text': str}, ...] sorted by time.
        Handles multiple tags per line, e.g. [00:10.50][00:20.50]Repeat verse
        and skips metadata headers like [ar:...], [ti:...].
        """
        if not lrc_text or not isinstance(lrc_text, str):
            return []

        tag_regex = re.compile(r"\[(\d{2}):(\d{2})(?:\.(\d{2,3}))?\]")
        lines = lrc_text.splitlines()
        entries = []

        for line in lines:
            matches = list(tag_regex.finditer(line))
            if not matches:
                continue
            text = tag_regex.sub("", line).strip()
            for m in matches:
                mins = int(m.group(1))
                secs = int(m.group(2))
                ms_str = m.group(3) or "0"
                ms_val = int(ms_str.ljust(3, "0")[:3])
                t = mins * 60 + secs + (ms_val / 1000.0)
                entries.append({"time": round(t, 3), "text": text})

        entries.sort(key=lambda x: x["time"])
        return entries

    @classmethod
    def fetch_lyrics(cls, title: str, artist: str, duration_sec: Optional[int] = None) -> Optional[Dict[str, str]]:
        """
        Fetches lyrics from LRCLIB.
        Returns dict with 'plain' and 'synced' lyrics if found, else None.
        """
        clean_title = cls.clean_text(title)
        clean_artist = cls.clean_text(artist)

        # 1. Try exact match endpoint
        params = {
            "track_name": clean_title or title,
            "artist_name": clean_artist or artist
        }
        if duration_sec and duration_sec > 0:
            params["duration"] = int(duration_sec)

        try:
            resp = requests.get(f"{cls.BASE_URL}/get", params=params, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                plain = data.get("plainLyrics")
                synced = data.get("syncedLyrics")
                if plain or synced:
                    return {"plain": plain or "", "synced": synced or ""}
        except Exception as e:
            logger.debug(f"Direct lyrics fetch error: {e}")

        # 2. Try search endpoint as fallback
        try:
            search_query = f"{clean_artist} {clean_title}".strip()
            resp = requests.get(f"{cls.BASE_URL}/search", params={"q": search_query}, timeout=5)
            if resp.status_code == 200:
                results = resp.json()
                if results and isinstance(results, list):
                    best = results[0]
                    plain = best.get("plainLyrics")
                    synced = best.get("syncedLyrics")
                    if plain or synced:
                        return {"plain": plain or "", "synced": synced or ""}
        except Exception as e:
            logger.debug(f"Search lyrics fetch error: {e}")

        return None

    @classmethod
    def embed_lyrics_to_mp3(
        cls,
        mp3_path: str,
        title: str,
        artist: str,
        duration_sec: Optional[int] = None,
        save_lrc_file: bool = True
    ) -> bool:
        """
        Fetches lyrics, embeds plain/synced lyrics into MP3 ID3 tags,
        and optionally writes a .lrc file in the same directory.
        """
        if not os.path.exists(mp3_path):
            return False

        lyrics = cls.fetch_lyrics(title, artist, duration_sec)
        if not lyrics:
            return False

        plain_lyrics = lyrics.get("plain", "")
        synced_lyrics = lyrics.get("synced", "")

        # Embed into MP3 ID3 tags
        try:
            audio = MP3(mp3_path, ID3=ID3)
            try:
                audio.add_tags()
            except Exception:
                pass

            if plain_lyrics:
                audio.tags.add(USLT(encoding=3, lang="eng", desc="Lyrics", text=plain_lyrics))

            if synced_lyrics:
                # Also store synced lyrics in standard TXXX:LYRICS tag for players supporting LRC text
                audio.tags.add(TXXX(encoding=3, desc="LYRICS", text=synced_lyrics))

            audio.save(v2_version=3)
        except Exception as e:
            logger.warning(f"Could not embed lyrics in {mp3_path}: {e}")

        # Write .lrc file alongside MP3 if synced lyrics are available
        if save_lrc_file and synced_lyrics:
            try:
                base_dir = os.path.dirname(mp3_path)
                base_name = os.path.splitext(os.path.basename(mp3_path))[0]
                lrc_path = os.path.join(base_dir, f"{base_name}.lrc")
                with open(lrc_path, "w", encoding="utf-8") as f:
                    f.write(synced_lyrics)
                logger.info(f"Saved synced lyrics file: {lrc_path}")
            except Exception as e:
                logger.warning(f"Could not save .lrc file: {e}")

        return True
