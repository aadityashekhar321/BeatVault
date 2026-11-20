"""
BeatVault Version & Release Metadata
Central source of truth for version tracking, metadata, and GitHub release synchronization.
"""

from typing import Dict, Any

__version__ = "1.0.0"

APP_NAME = "BeatVault"
APP_TITLE = "BeatVault - Music & Lyrics Studio"
APP_DESCRIPTION = "Studio-Grade Music Archival & Synchronized Lyrics Workstation"
AUTHOR = "Aaditya Shekhar"
AUTHOR_EMAIL = "aadityashekhar321@gmail.com"

# Repository and Release URLs
GITHUB_OWNER = "aadityashekhar321"
GITHUB_REPO = "BeatVault"
GITHUB_REPO_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}"
GITHUB_RELEASES_URL = f"{GITHUB_REPO_URL}/releases"
GITHUB_API_LATEST_RELEASE = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
RELEASE_NOTES_URL = f"{GITHUB_RELEASES_URL}/latest"


def get_version_info() -> Dict[str, Any]:
    """
    Returns application version and repository metadata as a serializable dict.
    """
    return {
        "version": __version__,
        "app_name": APP_NAME,
        "app_title": APP_TITLE,
        "app_description": APP_DESCRIPTION,
        "author": AUTHOR,
        "author_email": AUTHOR_EMAIL,
        "repo_owner": GITHUB_OWNER,
        "repo_name": GITHUB_REPO,
        "repo_url": GITHUB_REPO_URL,
        "releases_url": GITHUB_RELEASES_URL,
        "api_latest_release": GITHUB_API_LATEST_RELEASE,
        "release_notes_url": RELEASE_NOTES_URL,
    }
