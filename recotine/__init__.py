"""Recotine - Music recommendation and download automation tool.

Fetches recommendations from Last.fm and ListenBrainz, downloads tracks
via Nicotine++, and manages your music library with Navidrome.
"""

__version__ = "1.0.0"

# Import main CLI function for easy access
from recotine.main import cli

# Import key classes and functions for programmatic use
from recotine.cfg.config import load_config, RecotineConfig
from recotine.models import Track, Playlist, Links
from recotine.api.lastfm_api import create_lastfm_client
from recotine.api.listenbrainz_api import create_listenbrainz_client
from recotine.npp.docker_manager import DockerManager

__all__ = [
    "cli",
    "load_config", 
    "RecotineConfig",
    "Track",
    "Playlist", 
    "Links",
    "create_lastfm_client",
    "create_listenbrainz_client",
    "DockerManager",
]