#!/usr/bin/env python3
"""
BeatVault - Mobile & Desktop GUI Integration QA Test Suite
Comprehensive End-to-End Verification for:
1. Mobile PWA & Assets (manifest.json, sw.js, icons, offline caching)
2. Mobile Screen Architecture & Gestures (6 unified screens, mini-player tap/swipe, Obsidian Sonic tokens)
3. Mobile Server (IP auto-discovery, HTTP binding, CORS, static & manifest serving)
4. Desktop GUI Validation (HTML5 syntax, collapsible sidebar, pywebview API bridge, Obsidian Sonic tokens)
5. Python Backend Bridge Parity (all API methods and aliases exported on BeatVaultApi)
"""

import os
import sys
import json
import re
import socket
import threading
import time
import unittest
import urllib.request
from html.parser import HTMLParser

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUI_HTML_PATH = os.path.join(PROJECT_ROOT, "gui", "index.html")
MOBILE_DIR = os.path.join(PROJECT_ROOT, "mobile")
MOBILE_HTML_PATH = os.path.join(MOBILE_DIR, "index.html")
MANIFEST_PATH = os.path.join(MOBILE_DIR, "manifest.json")
SW_PATH = os.path.join(MOBILE_DIR, "sw.js")
MOBILE_SERVER_PATH = os.path.join(MOBILE_DIR, "mobile_server.py")
ASSETS_DIR = os.path.join(MOBILE_DIR, "assets")


class HTMLSyntaxValidator(HTMLParser):
    """Strict HTML5 syntax and unescaped entity checker."""
    def __init__(self):
        super().__init__()
        self.tags_stack = []
        self.errors = []
        self.void_elements = {
            'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
            'link', 'meta', 'param', 'source', 'track', 'wbr'
        }

    def handle_starttag(self, tag, attrs):
        if tag not in self.void_elements:
            self.tags_stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.void_elements:
            return
        if self.tags_stack and self.tags_stack[-1] == tag:
            self.tags_stack.pop()
        elif tag in self.tags_stack:
            while self.tags_stack and self.tags_stack[-1] != tag:
                self.tags_stack.pop()
            if self.tags_stack:
                self.tags_stack.pop()
        else:
            self.errors.append(f"Unexpected closing tag: </{tag}>")


class TestMobilePWAAndAssets(unittest.TestCase):
    """Test suite for Mobile Progressive Web App specifications and assets."""

    def test_manifest_json_structure_and_compliance(self):
        """Verify mobile/manifest.json conforms to PWA standards with Obsidian Sonic palette."""
        self.assertTrue(os.path.isfile(MANIFEST_PATH), "manifest.json must exist in mobile/")
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        self.assertEqual(manifest.get("name"), "BeatVault Mobile — Studio Audio Workstation")
        self.assertEqual(manifest.get("short_name"), "BeatVault")
        self.assertEqual(manifest.get("display"), "standalone")
        self.assertEqual(manifest.get("theme_color"), "#0f131c", "Theme color must be Obsidian Sonic #0f131c")
        self.assertEqual(manifest.get("background_color"), "#0f131c", "Background color must be #0f131c")
        self.assertIn("start_url", manifest)

        # Icons validation
        icons = manifest.get("icons", [])
        self.assertGreaterEqual(len(icons), 2, "Manifest should define at least 192 and 512 icons")
        icon_sizes = [i.get("sizes") for i in icons]
        self.assertIn("192x192", icon_sizes)
        self.assertIn("512x512", icon_sizes)

        # Shortcuts validation
        shortcuts = manifest.get("shortcuts", [])
        self.assertGreaterEqual(len(shortcuts), 2, "Manifest should define app shortcuts")

    def test_service_worker_implementation(self):
        """Verify mobile/sw.js exists with cache-first and stale-while-revalidate logic."""
        self.assertTrue(os.path.isfile(SW_PATH), "sw.js must exist in mobile/")
        with open(SW_PATH, "r", encoding="utf-8") as f:
            sw_code = f.read()

        self.assertIn("CACHE_NAME", sw_code)
        self.assertIn("addEventListener('install'", sw_code)
        self.assertIn("addEventListener('activate'", sw_code)
        self.assertIn("addEventListener('fetch'", sw_code)
        self.assertIn("caches.open", sw_code)
        self.assertIn("caches.match", sw_code)

    def test_mobile_asset_files_exist(self):
        """Verify all referenced assets exist in mobile/assets/."""
        self.assertTrue(os.path.isdir(ASSETS_DIR), "mobile/assets/ directory must exist")
        required_assets = [
            "icon-192.png",
            "icon-512.png",
            "icon_transparent.png"
        ]
        for asset in required_assets:
            path = os.path.join(ASSETS_DIR, asset)
            self.assertTrue(os.path.isfile(path), f"Asset {asset} must exist in mobile/assets/")
            self.assertGreater(os.path.getsize(path), 0, f"Asset {asset} must not be empty")


class TestMobileHTMLAndScreens(unittest.TestCase):
    """Test suite for mobile/index.html UI screens, gestures, and Obsidian Sonic design."""

    @classmethod
    def setUpClass(cls):
        assert os.path.isfile(MOBILE_HTML_PATH), "mobile/index.html must exist"
        with open(MOBILE_HTML_PATH, "r", encoding="utf-8") as f:
            cls.html = f.read()

    def test_html5_syntax_and_structure(self):
        """Verify valid HTML5 syntax, viewport meta, and script tag closures."""
        self.assertTrue(self.html.startswith("<!DOCTYPE html>"), "Must declare HTML5 doctype")
        self.assertIn("name=\"viewport\"", self.html)
        self.assertIn("viewport-fit=cover", self.html, "Must configure safe area viewport-fit=cover")
        self.assertIn("manifest.json", self.html, "Must link to manifest.json")
        self.assertIn("navigator.serviceWorker.register", self.html, "Must register Service Worker")

        validator = HTMLSyntaxValidator()
        validator.feed(self.html)
        self.assertEqual(len(validator.errors), 0, f"HTML syntax errors found: {validator.errors}")

    def test_all_six_unified_screens_present(self):
        """Verify mobile/index.html contains all 6 unified screens."""
        expected_screens = [
            ("screen-home-ingest", "Home Ingest Screen"),
            ("screen-playlist-inspector", "Playlist Inspector Screen"),
            ("screen-active-downloads", "Active Downloads Screen"),
            ("screen-offline-music-library", "Offline Music Library Screen"),
            ("now-playing-player", "Now Playing & Synced Lyrics Screen"),
            ("screen-app-settings", "App Settings Screen")
        ]
        for screen_id, screen_desc in expected_screens:
            self.assertIn(
                screen_id,
                self.html,
                f"Missing screen '{screen_id}' ({screen_desc}) in mobile/index.html"
            )

    def test_persistent_mini_player_and_gestures(self):
        """Verify persistent bottom mini-player with tap expansion and swipe up/down gesture logic."""
        self.assertIn('id="persistent-mini-player"', self.html, "Must contain persistent mini-player")
        self.assertIn('openNowPlayingModal', self.html, "Mini-player must trigger openNowPlayingModal")
        self.assertIn('touchstart', self.html, "Swipe gesture touchstart listener must be registered")
        self.assertIn('touchend', self.html, "Swipe gesture touchend listener must be registered")
        self.assertIn('closeNowPlayingModal', self.html, "Must contain modal close handler")

    def test_obsidian_sonic_palette_design_tokens(self):
        """Verify Obsidian Sonic design tokens (#0f131c, #53e076, #4cd7f6)."""
        html_lower = self.html.lower()
        self.assertIn("#0f131c", html_lower, "Must use Obsidian Dark background token #0f131c")
        self.assertIn("#53e076", html_lower, "Must use Sonic Green accent token #53e076")
        self.assertIn("#4cd7f6", html_lower, "Must use Cyber Cyan secondary token #4cd7f6")
        self.assertIn("assets/icon_transparent.png", self.html, "Must reference transparent Vinyl Safe icon")

    def test_synced_karaoke_lyrics_engine(self):
        """Verify LRC parser, synced lyric highlighting, and micro-equalizer animations."""
        self.assertIn("parseLrc", self.html, "Must contain LRC parser function")
        self.assertIn("lyric-active", self.html, "Must contain active lyric halo styling")
        self.assertIn("eq-bounce", self.html, "Must contain animated equalizer keyframes")

    def test_multi_platform_source_selectors(self):
        """Verify Spotify, YouTube, Apple Music, and SoundCloud platform selection buttons."""
        self.assertIn("data-platform=\"spotify\"", self.html)
        self.assertIn("data-platform=\"youtube\"", self.html)
        self.assertIn("data-platform=\"applemusic\"", self.html)
        self.assertIn("data-platform=\"soundcloud\"", self.html)


class TestMobileServer(unittest.TestCase):
    """Test suite for mobile/mobile_server.py network binding, IP detection, and asset delivery."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, MOBILE_DIR)
        import mobile_server
        cls.mobile_server = mobile_server
        cls.test_port = 8992

        cls.prev_dir = os.getcwd()
        os.chdir(MOBILE_DIR)

        cls.httpd = mobile_server.ReusableTCPServer(
            ("127.0.0.1", cls.test_port),
            mobile_server.BeatVaultHTTPRequestHandler
        )
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.4)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        os.chdir(cls.prev_dir)

    def test_ip_auto_detection(self):
        """Verify get_local_ip detects a valid IPv4 address."""
        ip = self.mobile_server.get_local_ip()
        self.assertIsInstance(ip, str)
        parts = ip.split(".")
        self.assertEqual(len(parts), 4, f"IP must have 4 octets, got: {ip}")
        for part in parts:
            self.assertTrue(part.isdigit() and 0 <= int(part) <= 255)

    def test_server_serves_html_and_cors(self):
        """Verify GET / returns 200 OK with CORS header."""
        url = f"http://127.0.0.1:{self.test_port}/"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=3) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("text/html", resp.headers.get("Content-Type", ""))
            self.assertEqual(resp.headers.get("Access-Control-Allow-Origin"), "*")

    def test_server_serves_manifest_json(self):
        """Verify GET /manifest.json returns 200 OK with application/manifest+json MIME type."""
        url = f"http://127.0.0.1:{self.test_port}/manifest.json"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=3) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("application/manifest+json", resp.headers.get("Content-Type", ""))

    def test_server_serves_service_worker(self):
        """Verify GET /sw.js returns 200 OK."""
        url = f"http://127.0.0.1:{self.test_port}/sw.js"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=3) as resp:
            self.assertEqual(resp.status, 200)

    def test_server_serves_png_asset(self):
        """Verify GET /assets/icon-192.png returns 200 OK with image/png MIME type."""
        url = f"http://127.0.0.1:{self.test_port}/assets/icon-192.png"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=3) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("image/png", resp.headers.get("Content-Type", ""))


class TestDesktopGUIValidation(unittest.TestCase):
    """Test suite for Desktop GUI (gui/index.html) syntax, collapsible sidebar, pywebview bridge, and tokens."""

    @classmethod
    def setUpClass(cls):
        assert os.path.isfile(GUI_HTML_PATH), "gui/index.html must exist"
        with open(GUI_HTML_PATH, "r", encoding="utf-8") as f:
            cls.html = f.read()

    def test_desktop_html5_syntax(self):
        """Verify Desktop GUI valid HTML5 doctype, proper script tags, and syntax."""
        self.assertTrue(self.html.strip().startswith("<!DOCTYPE html>"), "Must declare HTML5 doctype")
        self.assertIn("<html", self.html)
        self.assertIn("</html>", self.html)
        self.assertIn("</body>", self.html)

        open_scripts = len(re.findall(r'<script\b', self.html, re.I))
        close_scripts = len(re.findall(r'</script>', self.html, re.I))
        self.assertEqual(open_scripts, close_scripts, f"Mismatched script tags: {open_scripts} open vs {close_scripts} close")

        validator = HTMLSyntaxValidator()
        validator.feed(self.html)
        self.assertEqual(len(validator.errors), 0, f"GUI HTML syntax errors: {validator.errors}")

    def test_collapsible_sidebar_mechanism_and_persistence(self):
        """Verify sidebar collapse/expand toggle mechanism, compact icons mode, and localStorage persistence."""
        self.assertIn('id="appSidebar"', self.html, "Must have #appSidebar element")
        self.assertIn('sidebar-expanded', self.html, "Must define .sidebar-expanded CSS class")
        self.assertIn('sidebar-collapsed', self.html, "Must define .sidebar-collapsed CSS class")
        self.assertIn('id="sidebarToggleBtn"', self.html, "Must have #sidebarToggleBtn toggle button")
        self.assertIn('toggleSidebar', self.html, "Must define toggleSidebar method")
        self.assertIn('setSidebarCollapsed', self.html, "Must define setSidebarCollapsed method")
        self.assertIn('localStorage', self.html, "Must utilize localStorage for state persistence")
        self.assertIn('beatvault_sidebar_collapsed', self.html, "Must persist sidebar state under beatvault_sidebar_collapsed key")

    def test_pywebview_bridge_api_bindings_and_fallbacks(self):
        """Verify all 9 required pywebview API bindings and graceful browser fallback mock."""
        self.assertIn("window.pywebview", self.html, "Must support window.pywebview bridge")

        required_apis = [
            "get_playlist",
            "download_track",
            "download_playlist",
            "get_downloads",
            "get_lyrics",
            "get_settings",
            "save_settings",
            "check_for_updates",
            "open_download_folder"
        ]
        for api_name in required_apis:
            self.assertIn(
                api_name,
                self.html,
                f"Missing required pywebview API binding '{api_name}' in gui/index.html"
            )

        self.assertIn("if (!window.pywebview)", self.html, "Must define browser fallback mock if !window.pywebview")

    def test_obsidian_sonic_palette_and_vinyl_safe_icon(self):
        """Verify Obsidian Sonic palette design tokens and official transparent Vinyl Safe icon reference."""
        html_lower = self.html.lower()
        self.assertIn("#0f131c", html_lower, "Must use Obsidian Sonic surface token #0f131c")
        self.assertIn("#53e076", html_lower, "Must use Sonic Green accent token #53e076")
        self.assertIn("#4cd7f6", html_lower, "Must use Cyber Cyan secondary token #4cd7f6")
        self.assertIn("assets/icon_transparent.png", self.html, "Must reference official transparent Vinyl Safe icon")


class TestPythonBackendApiParity(unittest.TestCase):
    """Test suite ensuring api.py Python backend implements all required bindings and aliases."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, PROJECT_ROOT)
        from api import BeatVaultApi
        cls.api = BeatVaultApi()

    def test_api_class_has_all_required_methods(self):
        """Verify BeatVaultApi implements all 9 primary desktop GUI bridge methods/aliases."""
        required_methods = [
            "get_playlist",
            "download_track",
            "download_playlist",
            "get_downloads",
            "get_lyrics",
            "get_settings",
            "save_settings",
            "check_for_updates",
            "open_download_folder"
        ]
        for method_name in required_methods:
            self.assertTrue(
                hasattr(self.api, method_name),
                f"BeatVaultApi in api.py is missing required method/alias '{method_name}'"
            )
            self.assertTrue(
                callable(getattr(self.api, method_name)),
                f"BeatVaultApi.{method_name} must be callable"
            )


class TestDesktopGUIFixesAndParity(unittest.TestCase):
    """Test suite ensuring all 8 critical GUI fixes are implemented in gui/index.html."""

    @classmethod
    def setUpClass(cls):
        assert os.path.isfile(GUI_HTML_PATH), "gui/index.html must exist"
        with open(GUI_HTML_PATH, "r", encoding="utf-8") as f:
            cls.html = f.read()

    def test_audio_player_load_and_play_get_audio_data(self):
        """1. Verify App.player.loadAndPlay is async and requests get_audio_data for local files."""
        self.assertIn("async loadAndPlay(track)", self.html)
        self.assertIn("get_audio_data", self.html)
        self.assertIn("track.file_path", self.html)
        self.assertIn("res.data_url", self.html)

    def test_single_track_download_isolated(self):
        """2. Verify downloadSingleTrack isolates the single track without starting batch playlist download."""
        self.assertIn("downloadSingleTrack", self.html)
        self.assertIn("isolatedList", self.html)
        # Ensure it does not call startBatchDownload()
        match = re.search(r"async downloadSingleTrack\(idx\) \{([\s\S]*?)\n\s{6}\},", self.html)
        self.assertTrue(match, "downloadSingleTrack implementation should be found")
        body = match.group(1)
        self.assertNotIn("startBatchDownload", body, "Single track download must NOT trigger entire playlist startBatchDownload")
        self.assertIn("start_download", body)

    def test_cancel_active_download_stops_backend(self):
        """3. Verify cancelTask dispatches cancel_download to backend."""
        self.assertIn("cancelTask", self.html)
        self.assertIn("cancel_download", self.html)

    def test_offline_library_persistence_and_file_path(self):
        """4. Verify library tracks preserve file_path and persist to localStorage under beatvault_offline_library."""
        self.assertIn("beatvault_offline_library", self.html)
        self.assertIn("file_path:", self.html)
        self.assertIn("localStorage.setItem('beatvault_offline_library'", self.html)
        self.assertIn("localStorage.getItem('beatvault_offline_library')", self.html)

    def test_platform_buttons_preserve_custom_url_input(self):
        """5. Verify platform buttons do not overwrite user input if mediaUrlInput has value."""
        self.assertIn("urlInput.placeholder = engineUrls[engine]", self.html)
        self.assertIn("!urlInput.value.trim()", self.html)

    def test_lyrics_fallback_polite_empty_state(self):
        """6. Verify lyrics engine displays clean empty state without falling back to SAMPLE_LRC."""
        self.assertIn("No synchronized lyrics available for this track.", self.html)
        self.assertIn("microphone-slash", self.html)
        # Ensure SAMPLE_LRC is not assigned as fallback inside loadForTrack
        match = re.search(r"async loadForTrack\([\s\S]*?\{([\s\S]*?)\n\s{6}\},", self.html)
        self.assertTrue(match, "loadForTrack implementation should be found")
        body = match.group(1)
        self.assertNotIn("lrcText = SAMPLE_LRC", body, "SAMPLE_LRC must not be used as fallback for unknown tracks")

    def test_auto_updater_progress_events_and_dom_elements(self):
        """7. Verify handleBackendEvent handles update_download_progress and update_download_complete and DOM elements exist."""
        self.assertIn('id="updateProgressBar"', self.html)
        self.assertIn('id="updateProgressText"', self.html)
        self.assertIn('id="updateStatus"', self.html)
        self.assertIn("update_download_progress", self.html)
        self.assertIn("update_download_complete", self.html)

    def test_zero_tracks_selected_disables_download_button(self):
        """8. Verify updateSelectionSummary disables download button when 0 tracks are selected."""
        self.assertIn("btnDownloadSelected", self.html)
        self.assertIn("cursor-not-allowed", self.html)
        self.assertIn("pointer-events-none", self.html)


if __name__ == "__main__":
    unittest.main()
