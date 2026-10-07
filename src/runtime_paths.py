"""Helpers for resolving runtime paths in source and frozen builds."""

import ntpath
import os
import sys


def get_app_root() -> str:
    """Return the app root directory.

    In normal source runs, this is the repository root. In a frozen Windows
    build, it is the bundle content root (PyInstaller's internal directory)
    so bundled runtime folders like `static/`, `scripts/`, and `data/` stay
    together with the executable payload.
    """
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_default_data_dir() -> str:
    """Return the default path to the data directory.

    In normal runs, this is a 'data' subdirectory under the app root.
    In frozen builds, it is a persistent user directory (~/.odysseus/data)
    to prevent SQLite databases and other persistent files from being
    written to the ephemeral, temporary extraction bundle directory.
    """
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.expanduser("~"), ".odysseus", "data")
    return os.path.join(get_app_root(), "data")

_ONEDRIVE_ENV_VARS = ("OneDrive", "OneDriveCommercial", "OneDriveConsumer")


def is_inside_onedrive(path: str, environ=None) -> bool:
    """True when ``path`` lies in a Windows OneDrive-synced folder.

    OneDrive folders break the model downloader's cache (it stores files as
    links OneDrive can't hold: WinError 1920) and are a poor place for live
    databases. Matches the OneDrive roots Windows exports, plus any path
    component that starts with "OneDrive" for setups that don't export them.
    """
    env = os.environ if environ is None else environ
    norm = ntpath.normcase(ntpath.normpath(path))
    for var in _ONEDRIVE_ENV_VARS:
        root = env.get(var)
        if root:
            root = ntpath.normcase(ntpath.normpath(root)).rstrip("\\")
            if norm == root or norm.startswith(root + "\\"):
                return True
    return any(part.startswith("onedrive") for part in norm.split("\\"))


def default_fastembed_cache_dir(data_dir: str, environ=None, os_name: str = None) -> str:
    """Where FastEmbed keeps its model files when FASTEMBED_CACHE_PATH is unset.

    Normally ``<data_dir>/fastembed_cache``. On Windows with the data folder
    inside OneDrive, use ``%LOCALAPPDATA%\\maven\\fastembed_cache`` instead,
    so the download works and the model isn't synced to the cloud.
    """
    env = os.environ if environ is None else environ
    default = os.path.join(data_dir, "fastembed_cache")
    if (os_name or os.name) != "nt" or not is_inside_onedrive(data_dir, env):
        return default
    local = env.get("LOCALAPPDATA")
    if not local:
        return default
    return os.path.join(local, "maven", "fastembed_cache")
