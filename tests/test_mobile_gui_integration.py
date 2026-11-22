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


class TestDesktopCleanStateAndDynamicLogic(unittest.TestCase):
    """Test suite ensuring GUI initializes in a clean, professional, dynamic empty state without mock leaks."""

    @classmethod
    def setUpClass(cls):
        assert os.path.isfile(GUI_HTML_PATH), "gui/index.html must exist"
        with open(GUI_HTML_PATH, "r", encoding="utf-8") as f:
            cls.html = f.read()

    def test_media_url_input_empty_default(self):
        """1. Verify mediaUrlInput has an empty default value (no preset or hardcoded URL)."""
        match = re.search(r'<input id="mediaUrlInput"[^>]*>', self.html)
        self.assertTrue(match, "mediaUrlInput element must be present in HTML")
        tag = match.group(0)
        self.assertNotIn('value="http', tag, "mediaUrlInput must not contain a hardcoded URL in value attribute")
        self.assertNotIn('value="https://open.spotify.com', tag, "Spotify URL leak removed from mediaUrlInput")

    def test_no_sample_playlist_or_sample_library_in_app_init(self):
        """2. Verify App.init() does NOT auto-load SAMPLE_PLAYLIST or loadSampleLibrary() on startup."""
        match = re.search(r'async init\(\)\s*\{([\s\S]*?)\n\s{6}\}\n\s{4}\};', self.html)
        self.assertTrue(match, "App.init() method body must be located")
        init_body = match.group(1)
        self.assertNotIn("loadPlaylistData(SAMPLE_PLAYLIST)", init_body, "App.init must NOT load SAMPLE_PLAYLIST on startup")
        self.assertNotIn("loadSampleLibrary()", init_body, "App.init must NOT load sample library on startup")

    def test_inspector_empty_state_present(self):
        """3. Verify inspector empty state container exists and is configured for empty initial state."""
        self.assertIn('id="inspectorEmptyState"', self.html, "Inspector must define #inspectorEmptyState container")
        self.assertIn('id="inspectorContent"', self.html, "Inspector content must be wrapped in #inspectorContent")
        self.assertIn("No Tracks Loaded", self.html, "Inspector empty state must display 'No Tracks Loaded'")
        self.assertIn("manage_search", self.html, "Inspector empty state must feature manage_search icon")
        self.assertIn("Go to Ingest Gateway", self.html, "Action button to navigate to ingest must exist")

    def test_library_empty_state_and_clean_badges(self):
        """4. Verify library empty state container exists and default badges indicate 0 tracks cached."""
        self.assertIn('id="libraryEmptyState"', self.html, "Library must define #libraryEmptyState container")
        self.assertIn("Your Offline Vault is Empty", self.html, "Library empty state must display 'Your Offline Vault is Empty'")
        self.assertIn("Archive Music Now", self.html, "Library empty state action button must exist")
        self.assertIn("0 Tracks • 0 MB Cached", self.html, "Library header badge must default to 0 Tracks")
        self.assertIn("0% Lossless FLAC", self.html, "Library FLAC badge must default to 0%")

    def test_player_bar_initializes_in_clean_idle_state(self):
        """5. Verify player bar initializes in clean idle state (No Track Selected)."""
        self.assertIn('>No Track Selected<', self.html, "Player title must default to 'No Track Selected'")
        self.assertIn('>Select a track to play<', self.html, "Player artist must default to 'Select a track to play'")
        self.assertIn('>Standby<', self.html, "Player format badge must default to 'Standby'")
        
        # Scrubber and duration check
        dur_match = re.search(r'<span id="playerDuration"[^>]*>([^<]+)</span>', self.html)
        self.assertTrue(dur_match, "playerDuration element must exist")
        self.assertEqual(dur_match.group(1).strip(), "0:00", "Player duration must default to 0:00")

        # Player cover must not use hardcoded sample cover
        cover_match = re.search(r'<img id="playerCover"[^>]*src="([^"]+)"', self.html)
        self.assertTrue(cover_match, "playerCover element must exist")
        self.assertNotIn("photo-1614613535308", cover_match.group(1), "Player cover must not use hardcoded Unsplash sample image")

    def test_recent_ingests_clean_empty_state_and_persistence(self):
        """6. Verify recent ingests reads from beatvault_recent_ingests and renders clean empty state when empty."""
        self.assertIn("beatvault_recent_ingests", self.html, "Must use localStorage key beatvault_recent_ingests")
        self.assertIn("history_toggle_off", self.html, "Empty state must display history_toggle_off icon")
        self.assertIn("No recent ingests yet", self.html, "Empty state must display 'No recent ingests yet'")
        self.assertIn("URLs you analyze will be remembered here for quick access", self.html)

    def test_media_session_api_integration(self):
        """Verify OS Media Session API (System Media Transport Controls) integration."""
        self.assertIn("'mediaSession' in navigator", self.html, "Must check for mediaSession support")
        self.assertIn("navigator.mediaSession.metadata", self.html, "Must set MediaMetadata")
        self.assertIn("navigator.mediaSession.setActionHandler('play'", self.html, "Must set play action handler")
        self.assertIn("navigator.mediaSession.setActionHandler('pause'", self.html, "Must set pause action handler")
        self.assertIn("navigator.mediaSession.setActionHandler('previoustrack'", self.html, "Must set previoustrack action handler")
        self.assertIn("navigator.mediaSession.setActionHandler('nexttrack'", self.html, "Must set nexttrack action handler")
        self.assertIn("navigator.mediaSession.setActionHandler('seekto'", self.html, "Must set seekto action handler")
        self.assertIn("navigator.mediaSession.playbackState = 'playing'", self.html, "Must set playbackState to playing")
        self.assertIn("navigator.mediaSession.playbackState = 'paused'", self.html, "Must set playbackState to paused")

    def test_global_keyboard_shortcuts_and_audiophile_ux(self):
        """Verify global keyboard shortcuts with input guards and modal dismissals."""
        self.assertIn("document.addEventListener('keydown'", self.html, "Must register global keydown listener")
        self.assertIn("App.player.togglePlay()", self.html, "Space must trigger togglePlay")
        self.assertIn("App.player.toggleMute()", self.html, "KeyM must trigger toggleMute")
        self.assertIn("App.player.seekTo", self.html, "Arrow keys must trigger seekTo")
        self.assertIn("isContentEditable", self.html, "Must guard editable elements")
        self.assertIn("mediaUrlInput", self.html, "Shortcut must focus mediaUrlInput")

    def test_image_loading_failure_resilience(self):
        """Verify image fallback handler and global error capture."""
        self.assertIn("fallbackImage(imgElement)", self.html, "Must provide fallbackImage helper")
        self.assertIn("icon_transparent.png", self.html, "Must use safe transparent icon fallback")
        self.assertIn("window.addEventListener('error'", self.html, "Must have capture-phase error listener")

    def test_visualizer_power_optimization_visibilitychange(self):
        """Verify 60fps canvas visualizer stops rendering when tab/window is hidden."""
        self.assertIn("visibilitychange", self.html, "Must listen to visibilitychange")
        self.assertIn("document.hidden", self.html, "Must check document.hidden")
        self.assertIn("App.visualizer.stop()", self.html, "Must stop visualizer when document is hidden")

    def test_pywebview_bridge_guard_and_safe_ipc(self):
        """Verify pywebviewready listener log and unhandled rejection protection."""
        self.assertIn("PyWebView native bridge connected", self.html, "Must log PyWebView native bridge connected")
        self.assertIn("unhandledrejection", self.html, "Must handle unhandledrejection for safe IPC")

    def test_enhanced_time_and_size_formatting(self):
        """Verify formatTime supports hour-long audio (H:MM:SS) and formatBytes uses 1024 divisor."""
        self.assertIn("formatTime(sec)", self.html, "Must define formatTime")
        self.assertIn("3600", self.html, "formatTime must divide by 3600 for hour calculation")
        self.assertIn("formatBytes(bytes", self.html, "Must define formatBytes helper")
        self.assertIn("1024", self.html, "formatBytes must use 1024 divisor")


class TestMobileCleanStateAndDynamicLogic(unittest.TestCase):
    """Test suite ensuring Mobile GUI initializes in clean, dynamic empty state without mock leaks."""

    @classmethod
    def setUpClass(cls):
        assert os.path.isfile(MOBILE_HTML_PATH), "mobile/index.html must exist"
        with open(MOBILE_HTML_PATH, "r", encoding="utf-8") as f:
            cls.html = f.read()

    def test_mobile_url_input_no_preset_value(self):
        """1. Verify mobile url-input has no hardcoded value attribute."""
        match = re.search(r'<input id="url-input"[^>]*>', self.html)
        self.assertTrue(match, "url-input element must be present in mobile/index.html")
        tag = match.group(0)
        self.assertNotIn('value="', tag, "url-input must not contain a hardcoded value attribute")
        self.assertNotIn('value="https://open.spotify.com', tag, "Spotify URL leak removed from url-input")

    def test_no_preset_dummy_tracks_loaded_on_launch(self):
        """2. Verify mobile app initializes TRACKS_REPO, activeDownloads, completedDownloads, and inspectorTracks as empty arrays on launch."""
        self.assertIn("let TRACKS_REPO = [];", self.html, "TRACKS_REPO must initialize empty")
        self.assertIn("let activeDownloads = [];", self.html, "activeDownloads must initialize empty")
        self.assertIn("let completedDownloads = [];", self.html, "completedDownloads must initialize empty")
        self.assertIn("let inspectorTracks = [];", self.html, "inspectorTracks must initialize empty")
        self.assertIn("beatvault_mobile_library", self.html, "Must check localStorage beatvault_mobile_library")

    def test_mobile_inspector_empty_state_exists(self):
        """3. Verify #mobileInspectorEmptyState exists and displays elegant empty state when 0 tracks loaded."""
        self.assertIn('id="mobileInspectorEmptyState"', self.html, "Must have #mobileInspectorEmptyState container")
        self.assertIn("No Playlist Loaded", self.html, "Empty state must display 'No Playlist Loaded'")
        self.assertIn("Paste a music link on the Ingest screen", self.html)
        self.assertIn("Go to Ingest", self.html, "Must have 'Go to Ingest' button")
        self.assertIn('id="inspector-header-card"', self.html, "Inspector header must have #inspector-header-card")

    def test_mobile_vault_empty_state_exists(self):
        """4. Verify #mobileVaultEmptyState exists and displays elegant empty state when library is empty."""
        self.assertIn('id="mobileVaultEmptyState"', self.html, "Must have #mobileVaultEmptyState container")
        self.assertIn("Your Offline Vault is Empty", self.html, "Must display 'Your Offline Vault is Empty'")
        self.assertIn("Download Music Now", self.html, "Must have 'Download Music Now' button")
        self.assertIn('id="library-track-count">0 Tracks<', self.html, "Library track count must start at 0 Tracks")

    def test_mobile_mini_player_and_overlay_standby_state(self):
        """5. Verify mini player and now playing overlay start in idle/standby state."""
        self.assertIn('>No Track Playing<', self.html, "Mini player title must default to 'No Track Playing'")
        self.assertIn('>Choose a song from Vault or Queue<', self.html, "Mini player artist must default to Vault prompt")
        self.assertIn('>No Track Selected<', self.html, "Overlay title must default to 'No Track Selected'")
        self.assertIn('>Standby<', self.html, "Overlay artist must default to 'Standby'")
        self.assertIn('>Queue Empty<', self.html, "Overlay up next must default to 'Queue Empty'")
        self.assertIn('setPlayerIdleState', self.html, "Must define setPlayerIdleState method")

    def test_mobile_history_reads_local_storage_and_empty_state(self):
        """6. Verify mobile history reads from beatvault_mobile_history and has clean empty state."""
        self.assertIn("beatvault_mobile_history", self.html, "Must use localStorage beatvault_mobile_history key")
        self.assertIn('id="mobileHistoryEmptyState"', self.html, "Must define #mobileHistoryEmptyState")
        self.assertIn("No Recent Links", self.html, "Empty state must display 'No Recent Links'")
        self.assertTrue(re.search(r'id="history-count"[^>]*>0</span>', self.html), "History count must default to 0")

    def test_mobile_engine_auto_detection(self):
        """7. Verify engine auto-detection on typing/pasting for Spotify, YouTube, Apple Music, and SoundCloud."""
        self.assertIn("handleUrlInputChange", self.html, "Must define handleUrlInputChange handler")
        self.assertIn("spotify.com", self.html)
        self.assertIn("youtube.com", self.html)
        self.assertIn("apple.com", self.html)
        self.assertIn("soundcloud.com", self.html)

    def test_mobile_media_session_api_integration(self):
        """8. Verify Mobile Media Session API configuration for Android notification shade & lockscreen controls."""
        self.assertIn("'mediaSession' in navigator", self.html, "Must check for mediaSession support")
        self.assertIn("navigator.mediaSession.metadata", self.html, "Must set MediaMetadata")
        self.assertIn("navigator.mediaSession.setActionHandler('play'", self.html, "Must set play handler")
        self.assertIn("navigator.mediaSession.setActionHandler('pause'", self.html, "Must set pause handler")
        self.assertIn("navigator.mediaSession.setActionHandler('previoustrack'", self.html, "Must set prev handler")
        self.assertIn("navigator.mediaSession.setActionHandler('nexttrack'", self.html, "Must set next handler")


class TestLegacyFeaturesAdapted(unittest.TestCase):
    """Test suite ensuring all legacy UI/UX features are cleanly adapted into Obsidian Sonic GUI."""

    @classmethod
    def setUpClass(cls):
        assert os.path.isfile(GUI_HTML_PATH), "gui/index.html must exist"
        with open(GUI_HTML_PATH, "r", encoding="utf-8") as f:
            cls.html = f.read()

    def test_total_album_duration_badge_and_multi_format_summation(self):
        """1. Verify inspectorDurationBadge formats album length and parses ms/sec/formatted durations."""
        self.assertIn('id="inspectorDurationBadge"', self.html)
        self.assertIn("duration_ms", self.html)
        self.assertIn("duration_sec", self.html)
        self.assertIn("duration_formatted", self.html)
        self.assertIn("min", self.html)

    def test_pre_scan_folder_duplicates_and_auto_uncheck(self):
        """2. Verify scanFolderDuplicates pre-checks destination vault, tags Already in Vault, and auto-unchecks."""
        self.assertIn("scanFolderDuplicates", self.html)
        self.assertIn("scan_duplicates", self.html)
        self.assertIn("Already in Vault", self.html)
        self.assertIn("btnDeselectDuplicates", self.html)
        self.assertIn("deselectDuplicates", self.html)

    def test_inspector_filter_chips_and_search_filter(self):
        """3. Verify quick tracklist filter chips (All, Selected, Unselected, Vault) and search bar."""
        self.assertIn('id="inspectorFilterChips"', self.html)
        self.assertIn('id="inspectorSearchInput"', self.html)
        self.assertIn('id="btnClearInspectorSearch"', self.html)
        self.assertIn('id="chipFilterDuplicates"', self.html)
        self.assertIn('data-filter="all"', self.html)
        self.assertIn('data-filter="selected"', self.html)
        self.assertIn('data-filter="unselected"', self.html)

    def test_clipboard_fallback_graceful_prompt(self):
        """4. Verify clipboard paste failure provides prompt fallback for Linux/restricted WebViews."""
        self.assertIn("navigator.clipboard.readText", self.html)
        self.assertIn("prompt('Paste playlist or track URL", self.html)

    def test_theme_accent_swatches_and_persistence(self):
        """5. Verify Studio Theme Accent switcher (Green, Cyan, Purple, Orange) and localStorage persistence."""
        self.assertIn("theme-accent-btn", self.html)
        self.assertIn('data-theme-accent="green"', self.html)
        self.assertIn('data-theme-accent="cyan"', self.html)
        self.assertIn('data-theme-accent="purple"', self.html)
        self.assertIn('data-theme-accent="orange"', self.html)
        self.assertIn("setThemeAccent", self.html)
        self.assertIn("beatvault_theme_accent", self.html)


class TestAudioWorkstationAndGUILogicEnhancements(unittest.TestCase):
    """Test suite verifying user-requested audio workstation and GUI logic enhancements."""

    @classmethod
    def setUpClass(cls):
        assert os.path.isfile(GUI_HTML_PATH), "gui/index.html must exist"
        with open(GUI_HTML_PATH, "r", encoding="utf-8") as f:
            cls.gui_html = f.read()

        assert os.path.isfile(MOBILE_HTML_PATH), "mobile/index.html must exist"
        with open(MOBILE_HTML_PATH, "r", encoding="utf-8") as f:
            cls.mobile_html = f.read()

    def test_settings_recommended_badge_on_standard_quality(self):
        """1. Verify RECOMMENDED badge is associated with Standard (192 kbps) and removed from 320 kbps in GUI & Mobile."""
        match_320 = re.search(r'data-quality="320"[\s\S]*?Ultra Quality \(320 kbps\)[\s\S]*?</div>', self.gui_html)
        self.assertTrue(match_320, "Ultra Quality (320 kbps) section should exist in GUI")
        self.assertNotIn("RECOMMENDED", match_320.group(0), "Ultra Quality must not have RECOMMENDED badge in GUI")

        match_192 = re.search(r'data-quality="192"[\s\S]*?Standard \(192 kbps\)[\s\S]*?RECOMMENDED', self.gui_html)
        self.assertTrue(match_192, "Standard (192 kbps) section must feature RECOMMENDED badge in GUI")

        mobile_192 = re.search(r'value="192"[\s\S]*?Standard Quality — 192 kbps MP3[\s\S]*?RECOMMENDED', self.mobile_html)
        self.assertTrue(mobile_192, "Standard Quality 192 kbps must feature RECOMMENDED badge in mobile/index.html")

        mobile_320 = re.search(r'value="320"[\s\S]*?Ultra Quality — 320 kbps MP3[\s\S]*?HQ AUDIO', self.mobile_html)
        self.assertTrue(mobile_320, "Ultra Quality 320 kbps must feature HQ AUDIO badge in mobile/index.html, not RECOMMENDED")

    def test_inspector_target_quality_defaults_to_mp3(self):
        """2. Verify target quality in Inspector defaults to MP3 (192kbps) in both GUI & Mobile, not FLAC."""
        self.assertIn("targetQuality: 'mp3'", self.gui_html, "App.state.targetQuality must default to 'mp3'")
        
        mp3_btn_match = re.search(r'<button[^>]*data-quality="mp3"[^>]*>', self.gui_html)
        self.assertTrue(mp3_btn_match, "MP3 quality button must exist in HTML")
        self.assertIn("bg-primary-container", mp3_btn_match.group(0), "MP3 button must be styled as active (bg-primary-container)")

        flac_btn_match = re.search(r'<button[^>]*data-quality="flac"[^>]*>', self.gui_html)
        self.assertTrue(flac_btn_match, "FLAC quality button must exist in HTML")
        self.assertNotIn("bg-primary-container", flac_btn_match.group(0), "FLAC button must not be styled active by default")

        # Mobile Inspector target quality checks
        self.assertIn("inspectorTargetQuality = localStorage.getItem('beatvault_mobile_audio_quality') || '192'", self.mobile_html, "Mobile inspector quality must default to 192kbps from settings")
        self.assertIn("btn-insp-q-320", self.mobile_html, "Mobile inspector must feature MP3 320k selector button")
        self.assertIn("btn-insp-q-192", self.mobile_html, "Mobile inspector must feature MP3 192k selector button")

    def test_unified_version_synchronization(self):
        """Verify unified version 2.5.0 across GUI and Mobile files."""
        from version import __version__, BUILD_ID
        self.assertEqual(__version__, "1.6.9")
        self.assertEqual(BUILD_ID, "2026.11-STABLE")

        # Desktop GUI
        self.assertIn('id="settingsVersionBadge" class="text-on-surface-variant text-xs font-mono">v1.6.9-STABLE</span>', self.gui_html)
        self.assertIn('id="appBuildBadge" class="px-2 py-0.2 rounded bg-surface-container-highest text-secondary text-[10px] font-mono">v1.6.9</span>', self.gui_html)
        self.assertIn('id="modalCurrentVersion" class="font-mono text-on-surface">v1.6.9</span>', self.gui_html)

        # Mobile GUI
        self.assertIn('v1.6.9 (Build 2026.11)', self.mobile_html)

    def test_converting_to_mp3_status_in_downloader_and_queue(self):
        """3. Verify downloader emits converting status and both GUI & Mobile queues render dynamic 'Converting to MP3...' text."""
        from downloader import DownloadWorker
        worker = DownloadWorker([], "/fake/dest")
        track = {"title": "Test", "artist": "Artist", "id": "t1"}
        emitted = []
        worker.on_progress = lambda d: emitted.append(d)

        track["status"] = "converting"
        track["status_message"] = "Converting audio to MP3..."
        worker._emit_progress(track, 85.0)

        self.assertEqual(len(emitted), 1)
        self.assertEqual(emitted[0]["status"], "converting")
        self.assertEqual(emitted[0]["status_message"], "Converting audio to MP3...")
        self.assertEqual(emitted[0]["percent"], 85.0)

        # Desktop GUI queue checks
        self.assertIn("Converting to MP3...", self.gui_html)
        self.assertIn("t.status === 'converting'", self.gui_html)
        self.assertIn("animate-pulse", self.gui_html)

        # Mobile queue checks
        self.assertIn("Converting to MP3...", self.mobile_html)
        self.assertIn("task.status === 'converting'", self.mobile_html)

    def test_real_bandwidth_display_without_fake_multipliers(self):
        """4. Verify real bandwidth is tracked from download_progress and fake (activeCount * 2.4) is removed."""
        self.assertNotIn("(activeCount * 2.4)", self.gui_html, "Fake bandwidth multiplier (activeCount * 2.4) must be removed")
        self.assertIn("queueBandwidthVal", self.gui_html)
        self.assertIn("totalMBs", self.gui_html)

        # Mobile speed calculation checks
        self.assertIn("download-speed-ticker", self.mobile_html)
        self.assertIn("totalMBs", self.mobile_html, "Mobile queue must sum real speeds into totalMBs")

    def test_playback_controls_volume_and_context_navigation(self):
        """5. Verify volume controls (setVolume, mute toggle) and next/prev across multiple contexts (library, inspector, completed)."""
        # Desktop checks
        self.assertIn("setVolume(val)", self.gui_html)
        self.assertIn("btnPlayerMute", self.gui_html)
        self.assertIn("getActiveTrackList()", self.gui_html)
        self.assertIn("playbackContext", self.gui_html)

        # Mobile checks
        self.assertIn("setVolume(val)", self.mobile_html, "Mobile must feature setVolume handler")
        self.assertIn("player-volume-slider", self.mobile_html, "Mobile must feature volume slider")
        self.assertIn("btn-player-mute", self.mobile_html, "Mobile must feature mute toggle")
        self.assertIn("playbackContext", self.mobile_html, "Mobile must feature playbackContext tracking")
        self.assertIn("getActiveTrackList()", self.mobile_html, "Mobile must feature getActiveTrackList")
        self.assertIn("playInspectorTrack", self.mobile_html, "Mobile inspector must allow playing tracks")
        self.assertIn("playCompletedTrack", self.mobile_html, "Mobile queue must allow playing completed tracks")

    def test_lyrics_and_now_playing_song_thumbnail_display(self):
        """6. Verify lyrics modal & mini-player display song thumbnail instead of app logo when track is playing."""
        # Desktop GUI
        self.assertIn("const songCover = p.cover_url || p.cover || p.thumbnail;", self.gui_html)
        self.assertIn("npCover.classList.remove('opacity-30', 'p-12', 'object-contain');", self.gui_html)
        self.assertIn("npCover.classList.add('object-cover', 'opacity-100');", self.gui_html)

        # Mobile Mini-Player & Now Playing Overlay
        self.assertIn("getSongCover(track", self.mobile_html, "Mobile must use getSongCover helper")
        self.assertIn("miniCover.src = songCover;", self.mobile_html, "Mini cover must show playing song cover")
        self.assertIn("ovThumb.src = songCover;", self.mobile_html, "Now Playing thumb must show playing song cover")

    def test_dynamic_offline_storage_metrics(self):
        """7. Verify offline storage metrics in settings and vault compute real sizes without hardcoded FLAC 780MB."""
        self.assertIn("library-cached-size", self.mobile_html, "Vault header must feature library-cached-size id")
        self.assertIn("updateStorageFootprint()", self.mobile_html, "Settings must update dynamic storage footprint")
        self.assertIn("storage-audio-val", self.mobile_html, "Audio size must be dynamic in storage gauge")
        self.assertIn("storage-free-val", self.mobile_html, "Free space must be dynamic in storage gauge")

    def test_mobile_touch_gestures(self):
        """8. Verify pull-down gesture to dismiss Now Playing sheet and track card swipe interactions."""
        self.assertIn("now-playing-drag-handle", self.mobile_html, "Now playing sheet must have grab handle")
        self.assertIn("initNowPlayingGestures", self.mobile_html, "Now playing pull-down gesture must be initialized")
        self.assertIn("closeNowPlayingModal()", self.mobile_html)
        self.assertIn("openContextMenu", self.mobile_html, "Track card swipe must link to context actions")

    def test_pause_resume_buttons_and_api(self):
        """9. Verify download pause and resume buttons dispatch API calls and update UI state."""
        self.assertIn("btnPauseAll", self.gui_html)
        self.assertIn("btnResumeAll", self.gui_html)
        self.assertIn("pause_download", self.gui_html)
        self.assertIn("resume_download", self.gui_html)


class TestMobileServerAndServiceWorkerRobustness(unittest.TestCase):
    """Test suite verifying mobile_server.py MIME types, CORS, and sw.js cache strategies."""

    def test_mobile_server_mime_types(self):
        """Verify mobile_server.py maps audio, text LRC, manifest, and script MIME types accurately."""
        sys.path.insert(0, MOBILE_DIR)
        from mobile_server import BeatVaultHTTPRequestHandler

        # Create dummy instance for testing guess_type
        class DummyHandler(BeatVaultHTTPRequestHandler):
            def __init__(self):
                pass

        handler = DummyHandler()
        self.assertEqual(handler.guess_type("music.mp3"), "audio/mpeg")
        self.assertEqual(handler.guess_type("audio.flac"), "audio/flac")
        self.assertEqual(handler.guess_type("lyrics.lrc"), "text/plain; charset=utf-8")
        self.assertEqual(handler.guess_type("manifest.json"), "application/manifest+json")
        self.assertEqual(handler.guess_type("app.webmanifest"), "application/manifest+json")
        self.assertEqual(handler.guess_type("stream.opus"), "audio/opus")
        self.assertEqual(handler.guess_type("track.wav"), "audio/wav")
        self.assertEqual(handler.guess_type("track.m4a"), "audio/mp4")

    def test_mobile_server_cors_and_options_preflight(self):
        """Verify BeatVaultHTTPRequestHandler implements do_OPTIONS for CORS preflight on LAN."""
        from mobile_server import BeatVaultHTTPRequestHandler
        self.assertTrue(hasattr(BeatVaultHTTPRequestHandler, "do_OPTIONS"), "Handler must implement do_OPTIONS")

    def test_service_worker_cache_first_and_network_first_api(self):
        """Verify sw.js implements Cache-First for assets and Network-First for APIs with offline fallback."""
        with open(SW_PATH, "r", encoding="utf-8") as f:
            sw_code = f.read()

        self.assertIn("isAudioStream", sw_code, "Audio streams must bypass SW for range requests")
        self.assertIn("isApiRequest", sw_code, "API requests must be distinguished for Network-First strategy")
        self.assertIn("Offline mode active", sw_code, "Safe offline JSON fallback must be returned when offline")


class TestBackendIPCEdgeCasesAndSynchronization(unittest.TestCase):
    """Test suite verifying api.py edge-case resilience and downloader.py payload field consistency."""

    def setUp(self):
        from api import BeatVaultApi
        self.api = BeatVaultApi()

    def test_load_playlist_edge_cases(self):
        """load_playlist should handle None, empty strings, and malformed inputs gracefully."""
        res_empty = self.api.load_playlist("")
        self.assertFalse(res_empty["success"])
        self.assertIn("error", res_empty)

        res_none = self.api.load_playlist(None)
        self.assertFalse(res_none["success"])

        res_spaces = self.api.load_playlist("   ")
        self.assertFalse(res_spaces["success"])

    def test_get_audio_data_edge_cases_and_mime_types(self):
        """get_audio_data should handle non-existent files and detect appropriate audio MIME types."""
        res_missing = self.api.get_audio_data("non_existent_file.mp3")
        self.assertFalse(res_missing["success"])
        self.assertIn("error", res_missing)

        res_none = self.api.get_audio_data(None)
        self.assertFalse(res_none["success"])

    def test_scan_duplicates_edge_cases(self):
        """scan_duplicates should handle non-list tracks and invalid folder paths safely."""
        res_bad_folder = self.api.scan_duplicates([], "C:/Invalid/NonExistent/Folder/12345")
        self.assertFalse(res_bad_folder["success"])

        res_bad_tracks = self.api.scan_duplicates("not-a-list", self.api.get_default_folder())
        self.assertFalse(res_bad_tracks["success"])

    def test_downloader_payload_fields_consistency(self):
        """Ensure all payload fields (status, status_message, speed, eta, percent) are emitted."""
        from downloader import DownloadWorker
        worker = DownloadWorker([], "/fake/dest")
        track = {"title": "Test Title", "artist": "Test Artist", "id": "t1"}

        emitted_progress = []
        emitted_complete = []
        worker.on_progress = lambda d: emitted_progress.append(d)
        worker.on_track_complete = lambda d: emitted_complete.append(d)

        track["status"] = "downloading"
        track["status_message"] = "Downloading (4.2 MB/s)"
        worker._emit_progress(track, 45.0, "4.2 MB/s", "12s")

        self.assertEqual(len(emitted_progress), 1)
        p = emitted_progress[0]
        for field in ["status", "status_message", "speed", "eta", "percent"]:
            self.assertIn(field, p, f"Field '{field}' must be emitted in progress payload")

        track["status"] = "completed"
        track["status_message"] = "Completed"
        worker._emit_track_complete(track)

        self.assertEqual(len(emitted_complete), 1)
        c = emitted_complete[0]
        for field in ["status", "status_message", "speed", "eta", "percent"]:
            self.assertIn(field, c, f"Field '{field}' must be emitted in track_complete payload")


if __name__ == "__main__":
    unittest.main()
