"""ListenBrainz API integration for Recotine."""

from typing import List, Dict, Any, Optional

import requests

from recotine.cfg.config import RecotineConfig
from recotine.models import Playlist, Track, Links


def create_track_from_listenbrainz_data(track_data: Dict[str, Any]) -> Track:
    """Create Track from ListenBrainz API JSON data.

    Expected ListenBrainz structure:
    {
        "title": "track title",
        "creator": "primary artist",
        "identifier": ["https://musicbrainz.org/recording/<track_mbid>"],
        "extension": {
            "https://musicbrainz.org/doc/jspf#track": {
                "additional_metadata": {
                    "artists": [{
                            "artist_credit_name": "artist name",
                            "artist_mbid": "artist_mbid",
                            "join_phrase": ""
    }]}}}}

    Args:
        track_data: ListenBrainz track dictionary

    Returns:
        Track instance
    """

    title = track_data.get("title", "")

    # Extract artists from additional_metadata or fallback to creator
    artists = []
    try:
        extension = track_data.get("extension", {})
        jspf_data = extension.get("https://musicbrainz.org/doc/jspf#track", {})
        additional_metadata = jspf_data.get("additional_metadata", {})
        artist_data = additional_metadata.get("artists", [])

        for artist in artist_data:
            artist_name = artist.get("artist_credit_name", "")
            if artist_name:
                artists.append(artist_name)
    except (KeyError, TypeError):
        # Fallback to creator field
        creator = track_data.get("creator", "")
        if creator:
            artists = [creator]

    # If no artists found, use creator as fallback
    if not artists:
        creator = track_data.get("creator", "")
        if creator:
            artists = [creator]

    # Extract MBID from identifier
    mbid = None
    identifier = track_data.get("identifier", [])
    if identifier and len(identifier) > 0:
        mbid_url = identifier[0]
        if isinstance(mbid_url, str) and "recording/" in mbid_url:
            mbid = mbid_url.split("/")[-1]

    links = Links(mbid=mbid, url=None)

    return Track(title=title, artists=artists, links=links)


def create_playlist_from_listenbrainz_data(playlist_data: Dict[str, Any]) -> Playlist:
    """Create Playlist from ListenBrainz API JSON data.

    Expected ListenBrainz structure:
    {
        "title": "playlist title",
        "creator": "creator name",
        "identifier": "https://listenbrainz.org/playlist/<playlist_mbid>",
        "extension": {
            "https://musicbrainz.org/doc/jspf#playlist": {
                "additional_metadata": {
                    "algorithm_metadata": {
                        "source_patch": "weekly-exploration"
                    }},
                "creator": "creator name"
            }},
        "track": [list of tracks]
    }

    Args:
        playlist_data: ListenBrainz playlist dictionary

    Returns:
        Playlist instance
    """

    # Extract basic information
    title = playlist_data.get("title", "")
    creator = playlist_data.get("creator", "")

    # Try to enhance title with source_patch
    try:
        extension = playlist_data.get("extension", {})
        jspf_data = extension.get("https://musicbrainz.org/doc/jspf#playlist", {})
        additional_metadata = jspf_data.get("additional_metadata", {})
        algorithm_metadata = additional_metadata.get("algorithm_metadata", {})
        source_patch = algorithm_metadata.get("source_patch", "")

        if source_patch:
            title = f"{creator} {source_patch}"
    except (KeyError, TypeError):
        pass  # Use original title

    # Extract MBID from identifier
    mbid = None
    identifier = playlist_data.get("identifier", "")
    if isinstance(identifier, str) and "playlist/" in identifier:
        mbid = identifier.split("/")[-1]

    links = Links(mbid=mbid, url=identifier)

    # Convert tracks
    tracks = []
    track_data_list = playlist_data.get("track", [])
    for track_data in track_data_list:
        track = create_track_from_listenbrainz_data(track_data)
        tracks.append(track)

    return Playlist(title=title, creator=creator, links=links, tracks=tracks)


class ListenBrainzClient:
    """Client for interacting with ListenBrainz API."""
    
    BASE_URL = "https://api.listenbrainz.org/1"
    
    def __init__(self, config: RecotineConfig):
        """Initialize ListenBrainz client.
        
        Args:
            config: Recotine configuration instance
        """
        self.config = config
        self.username = config.listenbrainz_username
        self.user_token = config.listenbrainz_user_token
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Token {self.user_token}",
            "Content-Type": "application/json"
        })
    
    def get_user_playlists(self) -> List[Dict[str, Any]]:
        """Get all playlists for the user.
        
        Returns:
            List of playlist dictionaries
        """
        url = f"{self.BASE_URL}/user/{self.username}/playlists"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            return data.get("playlists", [])
        except requests.RequestException as e:
            print(f"Failed to fetch user playlists: {e}")
            return []
    
    def fetch_recommendations_playlists(self) -> List[Dict[str, Any]]:
        """Fetch createdfor/recommendation playlists from ListenBrainz recommendations API.
        
        Returns:
            List of recommendation playlist dictionaries
        """
        url = f"{self.BASE_URL}/user/{self.username}/playlists/createdfor"
        try:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()

            return data["playlists"]
        except requests.RequestException as e:
            print(f"Failed to fetch recommendations: {e}")
            return []

    def get_mbid_from_playlist(self, playlist: Dict[str, any]) -> Optional[str]:
        url = playlist["identifier"]

        if url:
            mbid = url.split('/')[-1]
            return mbid if mbid else None

    def get_playlist_from_mbid(self, mbid: str) -> Optional[Dict[str, Any]]:
        """Fetch playlist data using its MBID.
        
        Args:
            mbid: Playlist MBID
            
        Returns:
            Playlist dictionary, or None if not found
        """
        url = f"{self.BASE_URL}/playlist/{mbid}"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            return data.get('playlist')
        except requests.RequestException as e:
            print(f"Failed to fetch playlist {mbid}: {e}")
            return None

    def fetch_recommendations(self, source_patch: Optional[str] = None) -> List[Playlist]:
        """Fetch recommendations as unified Playlist objects.
        
        Args:
            source_patch: Optional filter for specific source patch (e.g., 'weekly-exploration', 'weekly-jams')
            
        Returns:
            List of unified Playlist objects
        """
        print(f"🎵 Fetching Listenbrainz recommendations for user: {self.username}")
        recs = self.fetch_recommendations_playlists()

        filtered_recs = []
        if source_patch:
            for playlist in recs:
                sp = playlist['playlist']['extension']['https://musicbrainz.org/doc/jspf#playlist']['additional_metadata']['algorithm_metadata']['source_patch']

                if sp == source_patch:
                    filtered_recs.append(playlist)

            recs = filtered_recs
        if not recs:
            return []

        # Get mbids of recommendation playlists
        mbids = [self.get_mbid_from_playlist(playlist['playlist']) for playlist in recs]
        rec_playlists = [self.get_playlist_from_mbid(mbid) for mbid in mbids if mbid]
        
        # Convert to unified format
        unified_playlists = []
        for playlist_data in rec_playlists:
            if playlist_data:
                unified_playlist = create_playlist_from_listenbrainz_data(playlist_data)
                unified_playlists.append(unified_playlist)
        
        return unified_playlists
    
    def fetch_and_save_recommendations(self, source_patch: Optional[str] = None) -> List[str]:
        """Fetch recommendations as unified structures and save to files.
        
        Args:
            source_patch: Optional filter for specific source patch
            
        Returns:
            List of saved file paths
        """
        playlists = self.fetch_recommendations(source_patch)
        
        saved_files = []
        for playlist in playlists:
            file_path = playlist.save_to_json()
            saved_files.append(file_path)
        
        return saved_files


def create_listenbrainz_client(config: RecotineConfig) -> ListenBrainzClient:
    """Create a ListenBrainz client instance.
    
    Args:
        config: Recotine configuration
        
    Returns:
        ListenBrainzClient instance
    """
    return ListenBrainzClient(config)