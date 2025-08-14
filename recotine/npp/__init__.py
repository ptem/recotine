"""Nicotine++ integration modules.

This module provides Docker management and search functionality for Nicotine++.
"""

from recotine.npp.docker_manager import DockerManager
from recotine.npp.npp_search import (
    TrackSearcher,
    PlaylistSearcher,
    search_track,
    download_track,
    search_playlist_file,
    search_all_playlists,
)

__all__ = [
    "DockerManager",
    "TrackSearcher",
    "PlaylistSearcher", 
    "search_track",
    "download_track",
    "search_playlist_file",
    "search_all_playlists",
]