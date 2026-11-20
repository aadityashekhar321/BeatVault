"""
BeatVault In-App Auto-Updater & GitHub Release Sync Service
Provides non-blocking GitHub releases querying, semver comparison,
background startup update notifications, and 1-click update installation.
"""

import os
import sys
import re
import json
import logging
import datetime
import threading
import webbrowser
from typing import Tuple, Optional, Dict, Any, Callable, List

import requests

from version import (
    __version__,
    APP_NAME,
    GITHUB_API_LATEST_RELEASE,
    GITHUB_RELEASES_URL,
    GITHUB_REPO_URL,
    get_version_info
)

logger = logging.getLogger("updater")


def parse_version(v_str: str) -> Tuple[int, ...]:
    """
    Parses a semver string (e.g. 'v1.2.3', '1.0.0', 'v2.1.0-beta') into a tuple of integers.
    Strips leading 'v' or 'V' and non-numeric suffixes for numeric comparison.
    """
    if not v_str:
        return (0, 0, 0)
    clean = str(v_str).strip().lstrip("vV")
    matches = re.findall(r"\d+", clean)
    if not matches:
        return (0, 0, 0)
    return tuple(int(x) for x in matches)


def is_newer_version(latest_v: str, current_v: str) -> bool:
    """
    Returns True if latest_v is strictly newer than current_v.
    Correctly handles different segment counts (e.g. 1.0 vs 1.0.1).
    """
    latest_tuple = parse_version(latest_v)
    current_tuple = parse_version(current_v)

    max_len = max(len(latest_tuple), len(current_tuple), 3)
    lat_padded = latest_tuple + (0,) * (max_len - len(latest_tuple))
    cur_padded = current_tuple + (0,) * (max_len - len(current_tuple))

    return lat_padded > cur_padded


def compare_semver(v1: str, v2: str) -> int:
    """
    Compares two version strings.
    Returns 1 if v1 > v2, 0 if v1 == v2, -1 if v1 < v2.
    """
    t1 = parse_version(v1)
    t2 = parse_version(v2)
    max_len = max(len(t1), len(t2), 3)
    p1 = t1 + (0,) * (max_len - len(t1))
    p2 = t2 + (0,) * (max_len - len(t2))

    if p1 > p2:
        return 1
    elif p1 < p2:
        return -1
    return 0


class UpdateChecker:
    """
    Asynchronous and synchronous GitHub release checker for BeatVault.
    Safely queries GitHub API with zero crashes on rate limits or offline state.
    """

    def __init__(self, current_version: str = __version__):
        self.current_version = current_version
        self.last_result: Optional[Dict[str, Any]] = None
        self.is_checking: bool = False

    def check_for_updates(self, manual: bool = False, timeout: int = 6) -> Dict[str, Any]:
        """
        Synchronously queries GitHub Releases API for the latest release.
        Returns a structured dictionary with update information.
        """
        self.is_checking = True
        result: Dict[str, Any] = {
            "success": False,
            "update_available": False,
            "current_version": self.current_version,
            "latest_version": self.current_version,
            "release_tag": f"v{self.current_version}",
            "release_name": "",
            "release_notes": "",
            "html_url": GITHUB_RELEASES_URL,
            "download_url": "",
            "published_at": "",
            "assets": [],
            "manual": manual,
            "checked_at": datetime.datetime.now().isoformat(),
            "status_message": "",
            "error": None,
        }

        headers = {
            "User-Agent": f"{APP_NAME}-AutoUpdater/{self.current_version}",
            "Accept": "application/vnd.github.v3+json",
        }

        try:
            resp = requests.get(GITHUB_API_LATEST_RELEASE, headers=headers, timeout=timeout)

            if resp.status_code == 200:
                data = resp.json()
                tag_name = data.get("tag_name", "").strip()
                release_name = data.get("name", "") or tag_name
                html_url = data.get("html_url", GITHUB_RELEASES_URL)
                body = data.get("body", "")
                published_at = data.get("published_at", "")
                raw_assets = data.get("assets", [])

                assets_list: List[Dict[str, Any]] = []
                installer_download_url = ""

                for a in raw_assets:
                    asset_info = {
                        "name": a.get("name", ""),
                        "size": a.get("size", 0),
                        "download_url": a.get("browser_download_url", ""),
                        "download_count": a.get("download_count", 0),
                    }
                    assets_list.append(asset_info)
                    name_lower = asset_info["name"].lower()
                    if name_lower.endswith(".exe") or "setup" in name_lower:
                        installer_download_url = asset_info["download_url"]

                if not installer_download_url and assets_list:
                    installer_download_url = assets_list[0].get("download_url", html_url)
                elif not installer_download_url:
                    installer_download_url = html_url

                clean_latest_v = tag_name.lstrip("vV") if tag_name else self.current_version
                has_update = is_newer_version(tag_name, self.current_version)

                result.update({
                    "success": True,
                    "update_available": has_update,
                    "latest_version": clean_latest_v,
                    "release_tag": tag_name,
                    "release_name": release_name,
                    "release_notes": body,
                    "html_url": html_url,
                    "download_url": installer_download_url,
                    "published_at": published_at,
                    "assets": assets_list,
                    "status_message": (
                        f"BeatVault v{clean_latest_v} is available!"
                        if has_update
                        else f"You're running the latest version of BeatVault (v{self.current_version})."
                    ),
                })
                logger.info(
                    f"Update check completed. Has update: {has_update} "
                    f"(latest: {tag_name}, current: {self.current_version})"
                )

            elif resp.status_code == 404:
                result.update({
                    "success": True,
                    "update_available": False,
                    "status_message": "No public releases found on GitHub repository.",
                    "html_url": GITHUB_RELEASES_URL,
                })
                logger.info("GitHub API returned 404: No releases yet.")

            elif resp.status_code in (403, 429):
                result.update({
                    "success": False,
                    "update_available": False,
                    "error": "rate_limited",
                    "status_message": "GitHub API rate limit exceeded. Please check back later.",
                    "html_url": GITHUB_RELEASES_URL,
                })
                logger.warning("GitHub API rate limit hit during update check.")

            else:
                result.update({
                    "success": False,
                    "update_available": False,
                    "error": f"http_{resp.status_code}",
                    "status_message": f"GitHub returned HTTP status {resp.status_code}.",
                    "html_url": GITHUB_RELEASES_URL,
                })
                logger.warning(f"GitHub API update check returned HTTP {resp.status_code}")

        except requests.exceptions.Timeout:
            result.update({
                "success": False,
                "update_available": False,
                "error": "timeout",
                "status_message": "Connection timed out while checking for updates.",
                "html_url": GITHUB_RELEASES_URL,
            })
            logger.info("Update check request timed out.")

        except requests.exceptions.RequestException as e:
            result.update({
                "success": False,
                "update_available": False,
                "error": "network_error",
                "status_message": "Unable to connect to GitHub. Check your internet connection.",
                "html_url": GITHUB_RELEASES_URL,
            })
            logger.info(f"Network error during update check: {e}")

        except Exception as e:
            result.update({
                "success": False,
                "update_available": False,
                "error": "unexpected_error",
                "status_message": f"Unexpected error checking updates: {e}",
                "html_url": GITHUB_RELEASES_URL,
            })
            logger.error(f"Unexpected error in update check: {e}")

        finally:
            self.is_checking = False
            self.last_result = result

        return result

    def check_for_updates_async(
        self,
        callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        manual: bool = False,
        delay_seconds: float = 0.0,
    ) -> threading.Thread:
        """
        Launches check_for_updates in a background daemon thread.
        Optional delay_seconds is useful for delayed startup checks.
        """
        import time

        def worker():
            if delay_seconds > 0:
                time.sleep(delay_seconds)
            res = self.check_for_updates(manual=manual)
            if callback:
                try:
                    callback(res)
                except Exception as cb_err:
                    logger.error(f"Error executing update callback: {cb_err}")

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        return thread


def open_release_page(url: Optional[str] = None) -> bool:
    """
    Opens the GitHub release page in the system default web browser.
    """
    target = url.strip() if url and url.strip() else GITHUB_RELEASES_URL
    try:
        webbrowser.open(target)
        return True
    except Exception as e:
        logger.error(f"Failed to open release page {target}: {e}")
        return False


def download_release_asset(
    download_url: str,
    dest_folder: Optional[str] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> Dict[str, Any]:
    """
    Downloads an installer or release asset file in chunks with progress reporting.
    Returns destination file path on success.
    """
    if not download_url:
        return {"success": False, "error": "No download URL provided"}

    target_dir = dest_folder or os.path.join(os.path.expanduser("~"), "Downloads")
    os.makedirs(target_dir, exist_ok=True)

    filename = download_url.split("/")[-1].split("?")[0]
    if not filename:
        filename = "BeatVault-Update.exe"

    target_path = os.path.join(target_dir, filename)

    try:
        with requests.get(download_url, stream=True, timeout=20) as r:
            r.raise_for_status()
            total_size = int(r.headers.get("content-length", 0))
            downloaded = 0

            with open(target_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total_size > 0:
                            progress_callback(downloaded, total_size)

        return {"success": True, "file_path": target_path, "file_name": filename}
    except Exception as e:
        logger.error(f"Error downloading update asset: {e}")
        return {"success": False, "error": str(e)}
