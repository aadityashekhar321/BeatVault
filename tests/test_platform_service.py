import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from platform_service import PlatformService
from spotify_service import SpotifyService


class TestSpotifyUrlParsing(unittest.TestCase):
    """Tests for SpotifyService.parse_spotify_url and duration formatting."""

    def test_spotify_uri_parsing(self):
        self.assertEqual(
            SpotifyService.parse_spotify_url("spotify:track:4cOdK2wGLETKBW3PvgPWqT"),
            {"type": "track", "id": "4cOdK2wGLETKBW3PvgPWqT"}
        )
        self.assertEqual(
            SpotifyService.parse_spotify_url("spotify:album:4aawyAB9vmqN3uQ7FjRGTy"),
            {"type": "album", "id": "4aawyAB9vmqN3uQ7FjRGTy"}
        )
        self.assertEqual(
            SpotifyService.parse_spotify_url("spotify:playlist:37i9dQZF1DXcBWIGoYBM5M"),
            {"type": "playlist", "id": "37i9dQZF1DXcBWIGoYBM5M"}
        )

    def test_spotify_web_urls(self):
        self.assertEqual(
            SpotifyService.parse_spotify_url("https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT"),
            {"type": "track", "id": "4cOdK2wGLETKBW3PvgPWqT"}
        )
        self.assertEqual(
            SpotifyService.parse_spotify_url("https://open.spotify.com/album/4aawyAB9vmqN3uQ7FjRGTy?si=abc123"),
            {"type": "album", "id": "4aawyAB9vmqN3uQ7FjRGTy"}
        )
        self.assertEqual(
            SpotifyService.parse_spotify_url("https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"),
            {"type": "playlist", "id": "37i9dQZF1DXcBWIGoYBM5M"}
        )

    def test_spotify_localized_intl_urls(self):
        self.assertEqual(
            SpotifyService.parse_spotify_url("https://open.spotify.com/intl-de/track/4cOdK2wGLETKBW3PvgPWqT"),
            {"type": "track", "id": "4cOdK2wGLETKBW3PvgPWqT"}
        )
        self.assertEqual(
            SpotifyService.parse_spotify_url("https://open.spotify.com/intl-ja/playlist/37i9dQZF1DXcBWIGoYBM5M?si=foo"),
            {"type": "playlist", "id": "37i9dQZF1DXcBWIGoYBM5M"}
        )

    def test_invalid_or_unsupported_spotify_urls(self):
        # Artist pages are not supported directly by parse_spotify_url
        self.assertIsNone(SpotifyService.parse_spotify_url("https://open.spotify.com/artist/06HL4z0CvFAxyc27GXpf02"))
        self.assertIsNone(SpotifyService.parse_spotify_url("https://google.com"))
        self.assertIsNone(SpotifyService.parse_spotify_url(""))
        self.assertIsNone(SpotifyService.parse_spotify_url(None))

    def test_format_duration(self):
        self.assertEqual(SpotifyService.format_duration(0), "0:00")
        self.assertEqual(SpotifyService.format_duration(-100), "0:00")
        self.assertEqual(SpotifyService.format_duration(60000), "1:00")
        self.assertEqual(SpotifyService.format_duration(185000), "3:05")
        self.assertEqual(SpotifyService.format_duration(212000), "3:32")


class TestPlatformDetection(unittest.TestCase):
    """Tests for PlatformService.detect_platform."""

    def setUp(self):
        self.service = PlatformService()

    def test_detect_spotify(self):
        self.assertEqual(self.service.detect_platform("https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"), "spotify")
        self.assertEqual(self.service.detect_platform("spotify:track:4cOdK2wGLETKBW3PvgPWqT"), "spotify")
        self.assertEqual(self.service.detect_platform("https://open.spotify.com/intl-es/album/123"), "spotify")

    def test_detect_youtube(self):
        self.assertEqual(self.service.detect_platform("https://www.youtube.com/watch?v=dQw4w9WgXcQ"), "youtube")
        self.assertEqual(self.service.detect_platform("https://youtu.be/dQw4w9WgXcQ"), "youtube")
        self.assertEqual(self.service.detect_platform("https://www.youtube.com/playlist?list=PL1234567890"), "youtube")
        self.assertEqual(self.service.detect_platform("https://music.youtube.com/watch?v=dQw4w9WgXcQ"), "youtube")
        self.assertEqual(self.service.detect_platform("https://music.youtube.com/playlist?list=OLAK5uy_k123"), "youtube")

    def test_detect_apple_music(self):
        self.assertEqual(self.service.detect_platform("https://music.apple.com/us/album/nevermind/1440783617"), "apple_music")
        self.assertEqual(self.service.detect_platform("https://music.apple.com/gb/playlist/todays-hits/pl.123"), "apple_music")
        self.assertEqual(self.service.detect_platform("https://itunes.apple.com/us/album/foo/12345"), "apple_music")

    def test_detect_soundcloud(self):
        self.assertEqual(self.service.detect_platform("https://soundcloud.com/artist/track-name"), "soundcloud")
        self.assertEqual(self.service.detect_platform("https://soundcloud.com/artist/sets/album-name"), "soundcloud")

    def test_detect_unknown(self):
        self.assertEqual(self.service.detect_platform("https://vimeo.com/123456"), "unknown")
        self.assertEqual(self.service.detect_platform("https://example.com/music"), "unknown")
        self.assertEqual(self.service.detect_platform(""), "unknown")
        self.assertEqual(self.service.detect_platform(None), "unknown")


class TestCleanYouTubeTitle(unittest.TestCase):
    """Tests for PlatformService._clean_youtube_title."""

    def test_cleans_artist_dash_title_with_official_tags(self):
        title, artist = PlatformService._clean_youtube_title(
            "The Weeknd - Blinding Lights (Official Video)", "Default Artist"
        )
        self.assertEqual(title, "Blinding Lights")
        self.assertEqual(artist, "The Weeknd")

    def test_cleans_brackets_and_visualizer_tags(self):
        title, artist = PlatformService._clean_youtube_title(
            "Dua Lipa - Levitating [Official Lyric Video]", "Default Artist"
        )
        self.assertEqual(title, "Levitating")
        self.assertEqual(artist, "Dua Lipa")

    def test_cleans_audio_hd_tags(self):
        title, artist = PlatformService._clean_youtube_title(
            "Queen - Bohemian Rhapsody (Audio) (4K)", "Default Artist"
        )
        self.assertEqual(title, "Bohemian Rhapsody")
        self.assertEqual(artist, "Queen")

    def test_no_dash_separator_uses_default_artist(self):
        title, artist = PlatformService._clean_youtube_title(
            "Blinding Lights (Official Music Video)", "The Weeknd"
        )
        self.assertEqual(title, "Blinding Lights")
        self.assertEqual(artist, "The Weeknd")

    def test_empty_title_returns_unknown(self):
        title, artist = PlatformService._clean_youtube_title("", "Fallback Artist")
        self.assertEqual(title, "Unknown Title")
        self.assertEqual(artist, "Fallback Artist")


class TestParseIso8601Duration(unittest.TestCase):
    """Tests for PlatformService._parse_iso8601_duration."""

    def test_minutes_and_seconds(self):
        self.assertEqual(PlatformService._parse_iso8601_duration("PT3M45S"), 225)
        self.assertEqual(PlatformService._parse_iso8601_duration("PT0M30S"), 30)

    def test_seconds_only(self):
        self.assertEqual(PlatformService._parse_iso8601_duration("PT45S"), 45)

    def test_hours_minutes_seconds(self):
        self.assertEqual(PlatformService._parse_iso8601_duration("PT1H2M3S"), 3723)

    def test_minutes_only(self):
        self.assertEqual(PlatformService._parse_iso8601_duration("PT5M"), 300)

    def test_empty_or_invalid(self):
        self.assertEqual(PlatformService._parse_iso8601_duration(""), 0)
        self.assertEqual(PlatformService._parse_iso8601_duration("INVALID"), 0)
        self.assertEqual(PlatformService._parse_iso8601_duration(None), 0)


class TestFetchMetadataRouter(unittest.TestCase):
    """Tests for unified PlatformService.fetch_metadata router dispatching."""

    def setUp(self):
        self.service = PlatformService()

    def test_empty_url_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.service.fetch_metadata("")
        with self.assertRaises(ValueError):
            self.service.fetch_metadata("   ")

    @patch.object(SpotifyService, "fetch_playlist_metadata")
    def test_routes_to_spotify(self, mock_fetch):
        mock_fetch.return_value = {
            "title": "Top Hits",
            "tracks": [{"title": "Song 1", "artist": "Artist 1"}]
        }
        url = "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
        result = self.service.fetch_metadata(url)

        self.assertEqual(result["platform"], "spotify")
        self.assertEqual(result["platform_name"], "Spotify")
        self.assertEqual(result["platform_badge"], "🟢 Spotify")
        self.assertEqual(result["tracks"][0]["platform"], "spotify")
        self.assertIsNone(result["tracks"][0]["direct_source_url"])

    @patch.object(PlatformService, "_fetch_youtube_metadata")
    def test_routes_to_youtube(self, mock_yt):
        mock_yt.return_value = {"platform": "youtube", "title": "YT Video", "tracks": []}
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        result = self.service.fetch_metadata(url)
        mock_yt.assert_called_once_with(url)
        self.assertEqual(result["platform"], "youtube")

    @patch.object(PlatformService, "_fetch_apple_music_metadata")
    def test_routes_to_apple_music(self, mock_apple):
        mock_apple.return_value = {"platform": "apple_music", "title": "Album", "tracks": []}
        url = "https://music.apple.com/us/album/nevermind/1440783617"
        result = self.service.fetch_metadata(url)
        mock_apple.assert_called_once_with(url)
        self.assertEqual(result["platform"], "apple_music")

    @patch.object(PlatformService, "_fetch_soundcloud_metadata")
    def test_routes_to_soundcloud(self, mock_sc):
        mock_sc.return_value = {"platform": "soundcloud", "title": "SoundCloud Track", "tracks": []}
        url = "https://soundcloud.com/artist/track-name"
        result = self.service.fetch_metadata(url)
        mock_sc.assert_called_once_with(url)
        self.assertEqual(result["platform"], "soundcloud")

    @patch.object(PlatformService, "_fetch_youtube_metadata", side_effect=Exception("Failed"))
    def test_unsupported_link_raises_value_error(self, mock_yt):
        with self.assertRaises(ValueError) as ctx:
            self.service.fetch_metadata("https://unsupported-site.com/media/123")
        self.assertIn("Unsupported or invalid link", str(ctx.exception))


class TestPlatformScraperParsers(unittest.TestCase):
    """Tests for YouTube, Apple Music, and SoundCloud internal parsing logic with mocks."""

    def setUp(self):
        self.service = PlatformService()

    @patch("yt_dlp.YoutubeDL")
    def test_youtube_single_video_parsing(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = {
            "title": "The Weeknd - Blinding Lights (Official Video)",
            "uploader": "The Weeknd",
            "duration": 200,
            "id": "4NRXx6U8ABQ",
            "webpage_url": "https://www.youtube.com/watch?v=4NRXx6U8ABQ",
            "thumbnails": [{"url": "https://img.youtube.com/vi/4NRXx6U8ABQ/hqdefault.jpg"}]
        }
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl

        res = self.service._fetch_youtube_metadata("https://www.youtube.com/watch?v=4NRXx6U8ABQ")
        self.assertEqual(res["platform"], "youtube")
        self.assertEqual(res["track_count"], 1)
        track = res["tracks"][0]
        self.assertEqual(track["title"], "Blinding Lights")
        self.assertEqual(track["artist"], "The Weeknd")
        self.assertEqual(track["duration_formatted"], "3:20")
        self.assertEqual(track["direct_source_url"], "https://www.youtube.com/watch?v=4NRXx6U8ABQ")

    @patch("yt_dlp.YoutubeDL")
    def test_youtube_playlist_parsing(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = {
            "title": "My Favorite Playlist",
            "uploader": "Curator",
            "entries": [
                {
                    "title": "Dua Lipa - Levitating",
                    "uploader": "Dua Lipa",
                    "duration": 203,
                    "id": "TUVcZfQe-Kw",
                    "thumbnails": [{"url": "https://img.youtube.com/thumb1.jpg"}]
                },
                {
                    "title": "Queen - Radio Ga Ga",
                    "uploader": "Queen",
                    "duration": 344,
                    "id": "azdwsXLmrHE",
                    "thumbnails": [{"url": "https://img.youtube.com/thumb2.jpg"}]
                }
            ]
        }
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl

        res = self.service._fetch_youtube_metadata("https://www.youtube.com/playlist?list=PL123")
        self.assertEqual(res["track_count"], 2)
        self.assertEqual(res["tracks"][0]["title"], "Levitating")
        self.assertEqual(res["tracks"][1]["title"], "Radio Ga Ga")
        self.assertEqual(res["tracks"][1]["duration_formatted"], "5:44")

    def test_apple_music_json_ld_parsing(self):
        sample_html = """
        <!DOCTYPE html>
        <html>
        <head>
          <script type="application/ld+json">
          {
            "@type": "MusicAlbum",
            "name": "Nevermind",
            "byArtist": [{"name": "Nirvana"}],
            "tracks": [
              {
                "name": "Smells Like Teen Spirit",
                "duration": "PT5M01S",
                "audio": {
                  "thumbnailUrl": "https://apple.com/cover.jpg",
                  "contentUrl": "https://apple.com/preview.mp3"
                }
              }
            ]
          }
          </script>
        </head>
        </html>
        """
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = sample_html

        with patch.object(self.service.session, "get", return_value=mock_resp):
            res = self.service._fetch_apple_music_metadata("https://music.apple.com/us/album/nevermind/1440783617")

            self.assertEqual(res["platform"], "apple_music")
            self.assertEqual(res["title"], "Nevermind")
            self.assertEqual(res["owner"], "Nirvana")
            self.assertEqual(res["track_count"], 1)
            track = res["tracks"][0]
            self.assertEqual(track["title"], "Smells Like Teen Spirit")
            self.assertEqual(track["duration_formatted"], "5:01")
            self.assertEqual(track["audio_preview"], "https://apple.com/preview.mp3")


if __name__ == "__main__":
    unittest.main()
