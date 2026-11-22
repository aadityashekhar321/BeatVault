import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from version import __version__, get_version_info
    from updater import (
        parse_version,
        is_newer_version,
        compare_semver,
        UpdateChecker
    )
    HAS_UPDATER = True
except ImportError:
    HAS_UPDATER = False

from api import AppAPI


@unittest.skipUnless(HAS_UPDATER, "updater module not available")
class TestSemverLogic(unittest.TestCase):
    """Tests for semver string parsing and comparison in updater module."""

    def test_parse_version(self):
        self.assertEqual(parse_version("v1.2.3"), (1, 2, 3))
        self.assertEqual(parse_version("1.0.0"), (1, 0, 0))
        self.assertEqual(parse_version("v2.0.0-beta.1"), (2, 0, 0, 1))
        self.assertEqual(parse_version(""), (0, 0, 0))
        self.assertEqual(parse_version(None), (0, 0, 0))

    def test_is_newer_version(self):
        self.assertTrue(is_newer_version("1.1.0", "1.0.0"))
        self.assertTrue(is_newer_version("1.0.1", "1.0.0"))
        self.assertTrue(is_newer_version("2.0.0", "1.9.9"))
        self.assertTrue(is_newer_version("v1.2.0", "1.1.9"))

        self.assertFalse(is_newer_version("1.0.0", "1.0.0"))
        self.assertFalse(is_newer_version("0.9.0", "1.0.0"))
        self.assertFalse(is_newer_version("1.0.0", "1.0.1"))

    def test_compare_semver(self):
        self.assertEqual(compare_semver("1.2.0", "1.1.0"), 1)
        self.assertEqual(compare_semver("1.0.0", "1.0.0"), 0)
        self.assertEqual(compare_semver("1.0.0", "1.0.1"), -1)


@unittest.skipUnless(HAS_UPDATER, "updater module not available")
class TestUpdateChecker(unittest.TestCase):
    """Tests for UpdateChecker GitHub API querying and asset extraction."""

    @patch("requests.get")
    def test_update_available_detected(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "tag_name": "v2.6.0",
            "name": "BeatVault v2.6.0 Release",
            "body": "## Features\n- Better karaoke sync\n",
            "html_url": "https://github.com/aadityashekhar321/BeatVault/releases/tag/v2.6.0",
            "assets": [
                {
                    "name": "BeatVault-Setup-v2.6.0.exe",
                    "browser_download_url": "https://github.com/releases/download/v2.6.0/installer.exe",
                    "size": 75000000
                }
            ]
        }
        mock_get.return_value = mock_resp

        checker = UpdateChecker(current_version="2.5.0")
        res = checker.check_for_updates()

        self.assertTrue(res["success"])
        self.assertTrue(res["update_available"])
        self.assertEqual(res["latest_version"], "2.6.0")
        self.assertEqual(res["download_url"], "https://github.com/releases/download/v2.6.0/installer.exe")
        self.assertEqual(len(res["assets"]), 1)
        self.assertEqual(res["assets"][0]["name"], "BeatVault-Setup-v2.6.0.exe")

    @patch("requests.get")
    def test_already_on_latest_version(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "tag_name": "v2.5.0",
            "name": "BeatVault v2.5.0",
            "body": "Latest release",
            "html_url": "https://github.com/releases/v2.5.0",
            "assets": []
        }
        mock_get.return_value = mock_resp

        checker = UpdateChecker(current_version="2.5.0")
        res = checker.check_for_updates()

        self.assertTrue(res["success"])
        self.assertFalse(res["update_available"])
        self.assertEqual(res["latest_version"], "2.5.0")

    @patch("requests.get", side_effect=Exception("Network unreachable"))
    def test_network_failure_handled_gracefully(self, mock_get):
        checker = UpdateChecker(current_version="2.5.0")
        res = checker.check_for_updates()

        self.assertFalse(res["success"])
        self.assertFalse(res["update_available"])
        self.assertEqual(res["error"], "unexpected_error")
        self.assertIn("unexpected error checking updates", res["status_message"].lower())


@unittest.skipUnless(HAS_UPDATER, "updater module not available")
class TestVersionInfo(unittest.TestCase):
    """Tests for version metadata and API integration."""

    def test_version_info_structure(self):
        info = get_version_info()
        self.assertEqual(__version__, "1.6.9")
        self.assertEqual(info["version"], "1.6.9")
        self.assertEqual(info["app_name"], "BeatVault")
        self.assertIn("github.com", info["repo_url"])

    def test_api_version_endpoint(self):
        api = AppAPI()
        res = api.get_version_info()
        self.assertTrue(res["success"])
        self.assertEqual(res["info"]["version"], __version__)


if __name__ == "__main__":
    unittest.main()
