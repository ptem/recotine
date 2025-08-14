"""API clients for music services.

This module provides API clients for Last.fm and ListenBrainz services.
"""

from recotine.api.lastfm_api import create_lastfm_client, LastFmClient
from recotine.api.listenbrainz_api import create_listenbrainz_client, ListenBrainzClient
from recotine.api.npp_api import NicotineAPI, SearchResult, SearchSortBy, NicotineAPIError

__all__ = [
    "create_lastfm_client",
    "LastFmClient", 
    "create_listenbrainz_client",
    "ListenBrainzClient",
    "NicotineAPI",
    "SearchResult", 
    "SearchSortBy",
    "NicotineAPIError",
]