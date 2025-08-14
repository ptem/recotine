"""Last.fm API integration for Recotine."""

import os
import requests
import pylast
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from config import RecotineConfig
from models import Playlist, Track, Links






class LastFmClient:
    """Client for interacting with Last.fm API."""
    
    def __init__(self, config: RecotineConfig):
        """Initialize Last.fm client.
        
        Args:
            config: Recotine configuration instance
        """
        self.config = config
        self.username = config.lastfm_username
        
        # Check if we have a session key, if not, prompt for authentication
        session_key = config.lastfm_session_key
        if not session_key:
            print("No Last.fm session key found in configuration.")
            print("Authentication required to access personalized features.")
            session_key = self.authenticate_lastfm()
        
        self.network = pylast.LastFMNetwork(
            api_key=config.lastfm_api_key,
            api_secret=config.lastfm_api_secret,
            username=config.lastfm_username,
            session_key=session_key
        )

    def create_track_from_lastfm_data(self, track_data: Dict[str, Any]) -> Track:
        """Create Track from Last.fm JSON data.

        Expected Last.fm structure:
        {
            "_name": "track title",
            "artists": [{"_name": "artist name"}, ...],
            "_playlinks": [{"url": "track_url"}, ...]
        }

        Args:
            track_data: Last.fm track dictionary

        Returns:
            Track instance
        """
        title = track_data.get("_name", "")

        # Extract artists
        artists = []
        artist_data = track_data.get("artists", [])
        for artist in artist_data:
            if isinstance(artist, dict):
                artist_name = artist.get("_name", "")
                if artist_name:
                    # Split comma-separated artist names to capture all collaborating artists
                    if ", " in artist_name:
                        split_artists = [name.strip() for name in artist_name.split(", ")]
                        artists.extend(split_artists)
                    else:
                        artists.append(artist_name)

        # Extract URL from playlinks
        url = None
        playlinks = track_data.get("_playlinks", [])
        if playlinks and len(playlinks) > 0:
            url = playlinks[0].get("url")
        links = Links(mbid=None, url=url)

        return Track(title=title, artists=artists, links=links)

    def create_playlist_from_lastfm_data(self, tracks_data: List[Dict[str, Any]]) -> Playlist:
        """Create Playlist from Last.fm track data.

        Args:
            tracks_data: List of Last.fm track dictionaries

        Returns:
            Playlist instance
        """
        title = "lastfm recommended"
        creator = "lastfm"
        links = Links(mbid=None, url=self.get_recommended_playlist_url())

        tracks = []
        for track_data in tracks_data:
            track = self.create_track_from_lastfm_data(track_data)
            tracks.append(track)

        return Playlist(title=title, creator=creator, links=links, tracks=tracks)

    def get_recommended_playlist_url(self) -> str:
        """Get the URL for the user's recommended playlist.
        
        Returns:
            URL string for the recommended playlist
        """
        return f"https://www.last.fm/player/station/user/{self.username}/recommended"
    
    def authenticate_lastfm(self) -> str:
        """Authenticate with Last.fm and get session key.
        
        This method guides the user through the Last.fm authentication process:
        1. Creates an authentication URL
        2. Prompts user to visit the URL and authorize the application
        3. Retrieves the session key after authorization
        
        Returns:
            Session key string for authenticated access
        """
        import webbrowser
        
        print("\n=== Last.fm Authentication ===")
        print("To access personalized Last.fm features, you need to authenticate.")
        
        # Create a temporary network instance for authentication
        network = pylast.LastFMNetwork(
            api_key=self.config.lastfm_api_key,
            api_secret=self.config.lastfm_api_secret
        )
        
        try:
            # Get authentication URL
            skg = pylast.SessionKeyGenerator(network)
            url = skg.get_web_auth_url()
            
            print(f"\n1. Please visit this URL to authorize the application:")
            print(f"   {url}")
            
            # Try to open the URL automatically
            try:
                webbrowser.open(url)
                print("   (Opening in your default browser...)")
            except:
                print("   (Could not open browser automatically)")
            
            print("\n2. After authorizing, press Enter to continue...")
            input()
            
            # Get the session key
            session_key = skg.get_web_auth_session_key(url)
            
            print(f"\n✓ Authentication successful!")
            print(f"Session key obtained: {session_key[:10]}...")
            print(f"\nTo avoid this step in the future, add the following to your config:")
            print(f"lastfm:")
            print(f"  session_key: {session_key}")
            
            return session_key
            
        except Exception as e:
            print(f"\n✗ Authentication failed: {e}")
            print("Please check your API credentials and try again.")
            raise

    def fetch_recommended_tracks(self) -> List[Dict[str, Any]]:
        """Fetch recommended tracks from Last.fm.

        This method fetches recommendations directly from the Last.fm recommended playlist JSON endpoint.
        This is more straightforward and reliable than using the pylast library.

        Returns:
            List of track dictionaries with full JSON data including URLs from _playlinks
        """
        tracks = []
        url = self.get_recommended_playlist_url()

        try:
            # Fetch recommendations directly from JSON endpoint
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            data = response.json()
            playlist = data.get('playlist', [])

            # Limit to configured max tracks
            max_tracks = self.config.playlists_max_tracks
            limited_playlist = playlist[:max_tracks] if max_tracks else playlist

            # Return full track data to preserve _playlinks and other metadata
            tracks = limited_playlist

        except requests.RequestException as e:
            print(f"Failed to fetch recommendations from JSON endpoint: {e}")
        except (KeyError, ValueError, TypeError) as e:
            print(f"Failed to parse recommendations JSON: {e}")

        return tracks


    def fetch_unified_recommendations(self) -> Playlist:
        """Fetch recommendations and return as unified Playlist object.

        Returns:
            Playlist object with unified structure
        """
        print(f"🎵 Fetching Last.fm recommendations for user: {self.username}")
        tracks_data = self.fetch_recommended_tracks()

        if not tracks_data:
            raise ValueError("No tracks found for Last.fm recommendations")

        # Convert to unified format using full JSON data
        playlist = self.create_playlist_from_lastfm_data(tracks_data)
        return playlist


    def fetch_and_save_unified_recommendations(self) -> Path:
        """Fetch recommendations as unified structure and save to file.
        
        Returns:
            Path to the saved playlist file
        """
        playlist = self.fetch_unified_recommendations()
        file_path = playlist.save_to_json()
        return file_path


def create_lastfm_client(config: RecotineConfig) -> LastFmClient:
    """Create a Last.fm client instance.
    
    Args:
        config: Recotine configuration
        
    Returns:
        LastFmClient instance
    """
    return LastFmClient(config)