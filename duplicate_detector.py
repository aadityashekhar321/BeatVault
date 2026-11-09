import os
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Dict, Any, Optional, List, Tuple
import mutagen
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3

class DuplicateDetector:
    def __init__(self, target_directory: str):
        self.target_directory = target_directory
        self._cache = {}
        self._cached_dir_mtime = 0
        self.refresh_cache()

    @staticmethod
    def sanitize_filename(name: str) -> str:
        """Removes illegal Windows characters from filename."""
        clean = re.sub(r'[\\/*?:"<>|]', "", name)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean or "untitled"

    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalizes a title or artist string for fuzzy comparison."""
        if not text:
            return ""
        # Decompose unicode characters (e.g. accents)
        text = unicodedata.normalize("NFKD", text).encode("ASCII", "ignore").decode("utf-8")
        text = text.lower()
        # Remove parenthetical extras like (feat. xyz), [official video], (lyrics), etc.
        text = re.sub(r"[\(\[\{].*?[\)\]\}]", " ", text)
        # Remove punctuation
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def similarity_ratio(a: str, b: str) -> float:
        """Returns SequenceMatcher ratio between two normalized strings."""
        return SequenceMatcher(None, a, b).ratio()

    def refresh_cache(self):
        """Scans the target directory and caches existing mp3 metadata."""
        if not os.path.exists(self.target_directory):
            self._cache = {}
            return

        current_files = {}
        try:
            for entry in os.scandir(self.target_directory):
                if entry.is_file() and entry.name.lower().endswith(".mp3"):
                    stat = entry.stat()
                    file_info = {
                        "path": entry.path,
                        "name": entry.name,
                        "size": stat.st_size,
                        "size_formatted": self.format_file_size(stat.st_size),
                        "mtime": stat.st_mtime,
                        "id3_title": "",
                        "id3_artist": "",
                        "normalized_name": self.normalize_text(os.path.splitext(entry.name)[0])
                    }

                    # Read ID3 tags if available
                    try:
                        audio = EasyID3(entry.path)
                        file_info["id3_title"] = audio.get("title", [""])[0]
                        file_info["id3_artist"] = audio.get("artist", [""])[0]
                    except Exception:
                        pass

                    current_files[entry.path] = file_info
        except Exception:
            pass

        self._cache = current_files

    @staticmethod
    def format_file_size(bytes_val: int) -> str:
        """Formats byte count to human-readable string (KB, MB)."""
        if bytes_val < 1024:
            return f"{bytes_val} B"
        elif bytes_val < 1024 * 1024:
            return f"{bytes_val / 1024:.1f} KB"
        else:
            return f"{bytes_val / (1024 * 1024):.2f} MB"

    def check_duplicate(self, title: str, artist: str) -> Optional[Dict[str, Any]]:
        """
        Checks if a song with the given title and artist already exists in the target directory.
        Returns details of the duplicate if found, or None.
        """
        # Always do a quick check if new files have been added to the folder
        if not self._cache:
            self.refresh_cache()

        norm_title = self.normalize_text(title)
        norm_artist = self.normalize_text(artist)

        best_match = None
        highest_score = 0.0

        for path, info in self._cache.items():
            # 1. Exact or near-exact ID3 Tag match
            if info["id3_title"]:
                norm_id3_title = self.normalize_text(info["id3_title"])
                norm_id3_artist = self.normalize_text(info["id3_artist"])

                title_ratio = self.similarity_ratio(norm_title, norm_id3_title)
                artist_ratio = self.similarity_ratio(norm_artist, norm_id3_artist) if norm_artist and norm_id3_artist else 1.0

                if title_ratio >= 0.88 and artist_ratio >= 0.75:
                    return {
                        "is_duplicate": True,
                        "match_type": "id3_tags",
                        "match_confidence": round((title_ratio + artist_ratio) / 2, 2),
                        "existing_file_path": path,
                        "existing_file_name": info["name"],
                        "existing_file_size": info["size_formatted"],
                        "existing_file_bytes": info["size"],
                        "reason": f"Matches audio tags: '{info['id3_title']}' by '{info['id3_artist']}'"
                    }

            # 2. Filename match
            norm_filename = info["normalized_name"]
            
            # Check if both artist and title are contained in the filename
            both_contained = (norm_title in norm_filename) and (not norm_artist or norm_artist in norm_filename)
            if both_contained:
                return {
                    "is_duplicate": True,
                    "match_type": "filename_exact",
                    "match_confidence": 0.95,
                    "existing_file_path": path,
                    "existing_file_name": info["name"],
                    "existing_file_size": info["size_formatted"],
                    "existing_file_bytes": info["size"],
                    "reason": f"Filename '{info['name']}' matches song title and artist"
                }

            # 3. Fuzzy filename match
            target_combo_1 = f"{norm_artist} {norm_title}".strip()
            target_combo_2 = f"{norm_title} {norm_artist}".strip()
            target_combo_3 = norm_title

            score1 = self.similarity_ratio(target_combo_1, norm_filename)
            score2 = self.similarity_ratio(target_combo_2, norm_filename)
            score3 = self.similarity_ratio(target_combo_3, norm_filename) if len(norm_title) > 6 else 0.0

            max_score = max(score1, score2, score3)
            if max_score > highest_score and max_score >= 0.83:
                highest_score = max_score
                best_match = {
                    "is_duplicate": True,
                    "match_type": "filename_fuzzy",
                    "match_confidence": round(max_score, 2),
                    "existing_file_path": path,
                    "existing_file_name": info["name"],
                    "existing_file_size": info["size_formatted"],
                    "existing_file_bytes": info["size"],
                    "reason": f"Filename '{info['name']}' is very similar to '{title} - {artist}' ({int(max_score * 100)}% match)"
                }

        return best_match

    def get_destination_filename(
        self,
        title: str,
        artist: str,
        track_index: int = 1,
        template: str = "title_artist",
        allow_copy: bool = True
    ) -> Tuple[str, str]:
        """
        Determines the output filename based on user-selected naming template:
        - 'title_artist': 'Song - Artist.mp3' (Default)
        - 'artist_title': 'Artist - Song.mp3'
        - 'track_title_artist': '01. Song - Artist.mp3'
        - 'title_only': 'Song.mp3'
        If allow_copy is True and the file already exists, appends (1), (2), etc.
        Guarantees existing files are never overwritten without explicit permission.
        Returns (full_path, basename).
        """
        clean_artist = self.sanitize_filename(artist)
        clean_title = self.sanitize_filename(title)

        if template == "artist_title" and clean_artist:
            base_name = f"{clean_artist} - {clean_title}"
        elif template == "track_title_artist":
            prefix = f"{int(track_index):02d}. " if track_index else ""
            if clean_artist:
                base_name = f"{prefix}{clean_title} - {clean_artist}"
            else:
                base_name = f"{prefix}{clean_title}"
        elif template == "title_only":
            base_name = clean_title
        else:  # default 'title_artist'
            if clean_artist:
                base_name = f"{clean_title} - {clean_artist}"
            else:
                base_name = clean_title

        ext = ".mp3"
        filename = f"{base_name}{ext}"
        full_path = os.path.join(self.target_directory, filename)

        if not allow_copy or not os.path.exists(full_path):
            return full_path, filename

        # Find safe incremental suffix
        counter = 1
        while True:
            candidate_filename = f"{base_name} ({counter}){ext}"
            candidate_path = os.path.join(self.target_directory, candidate_filename)
            if not os.path.exists(candidate_path):
                return candidate_path, candidate_filename
            counter += 1
