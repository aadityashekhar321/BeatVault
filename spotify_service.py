import re
import json
import logging
from typing import Dict, Any, List, Optional
import requests

logger = logging.getLogger("spotify_service")

class SpotifyService:
    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        })

    @staticmethod
    def parse_spotify_url(url: str) -> Optional[Dict[str, str]]:
        """
        Extracts resource type ('playlist', 'album', 'track') and Spotify ID from a given URL or URI.
        """
        if not url or not isinstance(url, str):
            return None
        url = url.strip()

        # Check for spotify:type:id URI
        uri_match = re.match(r"^spotify:(playlist|album|track):([a-zA-Z0-9]+)", url)
        if uri_match:
            return {"type": uri_match.group(1), "id": uri_match.group(2)}

        # Check for open.spotify.com URL
        url_match = re.search(r"open\.spotify\.com/(intl-[a-z]+/)?(playlist|album|track)/([a-zA-Z0-9]+)", url)
        if url_match:
            return {"type": url_match.group(2), "id": url_match.group(3)}

        return None

    @staticmethod
    def format_duration(ms: int) -> str:
        """Formats milliseconds into mm:ss."""
        if not ms or ms <= 0:
            return "0:00"
        total_seconds = int(ms / 1000)
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}:{seconds:02d}"

    def fetch_playlist_metadata(self, url: str) -> Dict[str, Any]:
        """
        Fetches metadata and tracklist for a Spotify playlist, album, or track without requiring DRM bypass.
        Returns a dictionary containing title, description, cover image, and list of tracks.
        """
        parsed = self.parse_spotify_url(url)
        if not parsed:
            raise ValueError(
                "Invalid Spotify URL. Please provide a valid playlist URL like "
                "https://open.spotify.com/playlist/..."
            )

        res_type = parsed["type"]
        res_id = parsed["id"]

        embed_url = f"https://open.spotify.com/embed/{res_type}/{res_id}"
        logger.info(f"Fetching Spotify embed metadata from {embed_url}")

        try:
            resp = self.session.get(embed_url, timeout=15)
        except requests.RequestException as e:
            raise ConnectionError(f"Network error connecting to Spotify: {str(e)}")

        if resp.status_code == 404:
            raise ValueError("The requested Spotify playlist or album could not be found (404). It may be private or deleted.")
        elif resp.status_code != 200:
            raise ValueError(f"Spotify returned status code {resp.status_code}. Please check the URL.")

        # Extract __NEXT_DATA__ JSON from HTML
        match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', resp.text, re.DOTALL)
        if not match:
            # Fallback search for any JSON containing trackList
            match = re.search(r'data-resource="([^"]+)"', resp.text)
            if not match:
                raise ValueError("Could not extract track data from Spotify playlist page.")

        try:
            data = json.loads(match.group(1))
        except Exception as e:
            raise ValueError(f"Failed to parse Spotify metadata JSON: {str(e)}")

        props = data.get("props", {}).get("pageProps", {})
        state = props.get("state", {})
        entity = state.get("data", {}).get("entity", {})

        if not entity:
            raise ValueError("Playlist data was empty. The playlist might be private or empty.")

        title = entity.get("title") or entity.get("name") or "Untitled Playlist"
        subtitle = entity.get("subtitle") or ""
        authors = entity.get("authors", [])
        author_name = authors[0].get("name", "") if authors else subtitle

        # Extract cover art
        cover_url = ""
        visual = entity.get("visualIdentity", {})
        images = visual.get("image", []) or entity.get("images", [])
        if images:
            # Prefer medium or high resolution (index 1 or 2 if available, else last)
            if len(images) > 1:
                cover_url = images[1].get("url") or images[-1].get("url")
            else:
                cover_url = images[0].get("url", "")

        raw_tracks = entity.get("trackList", [])
        
        # If it's a single track, trackList might be empty but entity itself is the track
        if not raw_tracks and res_type == "track":
            raw_tracks = [entity]

        tracks = []
        for index, item in enumerate(raw_tracks):
            track_title = item.get("title") or item.get("name") or f"Track {index + 1}"
            track_artist = item.get("subtitle") or ""
            
            # If artists is a list
            if not track_artist and "artists" in item:
                artists_list = item.get("artists", [])
                track_artist = ", ".join(a.get("name", "") for a in artists_list if isinstance(a, dict))

            duration_ms = item.get("duration", 0)
            uri = item.get("uri", "")

            # Audio preview if available
            audio_preview = item.get("audioPreview", {}).get("url") if isinstance(item.get("audioPreview"), dict) else None

            tracks.append({
                "index": index + 1,
                "id": uri or f"track_{index + 1}",
                "uri": uri,
                "title": track_title.strip(),
                "artist": track_artist.strip(),
                "duration_ms": duration_ms,
                "duration_formatted": self.format_duration(duration_ms),
                "cover_url": "",
                "audio_preview": audio_preview,
                "status": "queued",
                "status_message": "Queued",
                "progress": 0,
                "selected": True,
                "duplicate_info": None
            })

        return {
            "type": res_type,
            "id": res_id,
            "title": title.strip(),
            "author": author_name.strip(),
            "cover_url": cover_url,
            "total_tracks": len(tracks),
            "tracks": tracks
        }
