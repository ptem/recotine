"""Track search functionality utilizing npp_api, models, and config.

This module provides track-specific search and download functionality that builds
upon the core NPP API but is not strictly part of the API itself.
"""

import json
import logging
import time
from pathlib import Path
from typing import Optional, List, Dict

from recotine.api.npp_api import NicotineAPI, SearchResult, SearchSortBy, NicotineAPIError
from recotine.cfg.config import load_config, RecotineConfig
from recotine.models import Track, Playlist, Links
from recotine.paths import OUTPUT_DIR

logger = logging.getLogger(__name__)


class TrackSearcher:
    """
    Handles searching and downloading tracks using the Nicotine++ API.
    
    This class provides high-level track search functionality that utilizes
    the npp_api, models, and config modules but isn't strictly part of the core API.
    """
    
    def __init__(self, api_url: str = "http://localhost:7770", timeout: int = 30):
        """
        Initialize the TrackSearcher.
        
        Args:
            api_url: Base URL for the Nicotine++ API
            timeout: Request timeout in seconds
        """
        self.api = NicotineAPI(api_url, timeout)
    
    def search_track(self, 
                    track: Track, 
                    config: Optional[RecotineConfig] = None) -> List[SearchResult]:
        """
        Search for a track using NPP API with configuration-based filtering
        
        Args:
            track: Track object containing title and artists
            config: RecotineConfig instance with NPP search settings (optional)
            
        Returns:
            List of SearchResult objects matching the track
            
        Raises:
            NicotineAPIError: If search fails
        """
        # Load config if not provided
        if config is None:
            config = load_config()
        
        # Prepare search queries using fallback strategies
        fallback_strategies = config.npp_search_fallback_strategies
        artist_str = ", ".join(track.artists) if track.artists else ""
        
        queries = []
        for strategy in fallback_strategies:
            if strategy == "artist title" and artist_str:
                queries.append(f"{artist_str} {track.title}")
            elif strategy == '"artist" "title"' and artist_str:
                queries.append(f'"{artist_str}" "{track.title}"')
            elif strategy == "title artist" and artist_str:
                queries.append(f"{track.title} {artist_str}")
            elif strategy == '"artist" with title includes' and artist_str:
                # Use quoted artist as query, but add title to includes_text
                queries.append((f'"{artist_str}"', [track.title]))
            elif strategy == "title":
                queries.append(track.title)
        
        # If no artists provided, just use title
        if not queries:
            queries = [track.title]
        
        logger.info(f"Searching for track: {track}")
        logger.info(f"Using {len(queries)} fallback strategies: {queries}")
        
        all_results = []
        max_attempts = config.npp_search_max_attempts
        
        # Try each query strategy until we get good results or exhaust attempts
        for attempt, query_info in enumerate(queries[:max_attempts], 1):
            if isinstance(query_info, tuple):
                query, custom_includes = query_info
                includes_text = list(config.npp_search_require_terms) + custom_includes
            else:
                query = query_info
                includes_text = config.npp_search_require_terms
                
            logger.info(f"Attempt {attempt}: Searching with query '{query}'")
            if isinstance(query_info, tuple):
                logger.info(f"   Additional includes_text: {custom_includes}")
            
            try:
                results = self.api.search_and_filter(
                    query=query,
                    min_bitrate=config.npp_search_min_bitrate,
                    max_file_size_mb=config.npp_search_max_file_size_mb,
                    min_similarity=config.npp_search_min_similarity,
                    require_free_slots=config.npp_search_require_free_slots,
                    file_extensions=config.npp_search_allowed_extensions,
                    sort_by=SearchSortBy.SIMILARITY,
                    wait_time=config.npp_search_max_wait_time,
                    includes_text=includes_text,
                    excludes_text=config.npp_search_exclude_terms
                )
                
                if results:
                    logger.info(f"Found {len(results)} results with query '{query}'")
                    all_results.extend(results)
                    
                    # If we have good quality results, we can stop early
                    sufficient_threshold = config.npp_search_sufficient_similarity
                    high_similarity_results = [r for r in results if r.search_similarity >= sufficient_threshold]
                    if high_similarity_results:
                        logger.info(f"Found {len(high_similarity_results)} results with sufficient similarity (>= {sufficient_threshold}), stopping search")
                        break
                else:
                    logger.info(f"No results found with query '{query}'")
                    
            except Exception as e:
                logger.warning(f"Search attempt {attempt} failed: {e}")
                continue
        
        # Remove duplicates (same user + file path) and sort by similarity
        seen = set()
        unique_results = []
        for result in all_results:
            key = (result.user, result.file_path)
            if key not in seen:
                seen.add(key)
                unique_results.append(result)
        
        # Sort by similarity (best first)
        unique_results.sort(key=lambda x: x.search_similarity, reverse=True)
        
        logger.info(f"Track search completed: {len(unique_results)} unique results for '{track}'")
        return unique_results

    def download_best_result(self, 
                           track: Track, 
                           config: Optional[RecotineConfig] = None) -> Optional[str]:
        """
        Search for a track and download the best result.
        
        Args:
            track: Track object to search for
            config: RecotineConfig instance (optional)
            
        Returns:
            Download response message or None if no suitable results found
            
        Raises:
            NicotineAPIError: If API is not available or download fails
        """
        # Check API availability
        if not self.api.is_available():
            raise NicotineAPIError("Nicotine++ API is not available")
        
        # Load config if not provided
        if config is None:
            config = load_config()
        
        # Search for the track
        results = self.search_track(track, config)
        
        if not results:
            logger.warning(f"No suitable results found for track: {track}")
            return None
        
        # Use the API's download_best_result method with the search results
        return self.api.download_best_result(
            results, 
            prefer_free_slots=config.npp_search_require_free_slots,
            min_bitrate=config.npp_search_min_bitrate
        )

    def search_and_download_track(self,
                                 track: Track,
                                 config: Optional[RecotineConfig] = None) -> Optional[str]:
        """
        Convenience method that combines search and download for a track.
        
        Args:
            track: Track object to search for and download
            config: RecotineConfig instance (optional)
            
        Returns:
            Download response message or None if no suitable results found
        """
        return self.download_best_result(track, config)


class PlaylistSearcher:
    """
    Handles searching and downloading tracks from playlists using TrackSearcher.
    
    This class works with JSON playlists (using models.Playlist) and provides 
    comprehensive reporting of search results and failures.
    """
    
    def __init__(self, api_url: str = "http://localhost:7770", timeout: int = 30, output_dir: Optional[Path] = None):
        """
        Initialize the PlaylistSearcher.
        
        Args:
            api_url: Base URL for the Nicotine++ API
            timeout: Request timeout in seconds
            output_dir: Base output directory for downloads (defaults to ./output/playlists/)
        """
        self.track_searcher = TrackSearcher(api_url, timeout)
        self.output_dir = output_dir or Path("output/playlists")
        self.stats = {
            "total_tracks": 0,
            "successful_downloads": 0,
            "failed_searches": 0,
            "api_errors": 0
        }
    
    def parse_json_playlist(self, playlist_path: Path) -> Playlist:
        """
        Parse a JSON playlist file into a Playlist object.
        
        Args:
            playlist_path: Path to the JSON playlist file
            
        Returns:
            Playlist object
            
        Raises:
            ValueError: If the file cannot be parsed
        """
        try:
            with open(playlist_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Create Links object
            links_data = data.get("links", {})
            links = Links(mbid=links_data.get("mbid"), url=links_data.get("url"))
            
            # Create Track objects
            tracks = []
            for track_data in data.get("tracks", []):
                track_links_data = track_data.get("links", {})
                track_links = Links(mbid=track_links_data.get("mbid"), url=track_links_data.get("url"))
                
                track = Track(
                    title=track_data["title"],
                    artists=track_data.get("artists", []),
                    links=track_links
                )
                tracks.append(track)
            
            playlist = Playlist(
                title=data["title"],
                creator=data["creator"],
                links=links,
                tracks=tracks
            )
            
            logger.info(f"Parsed JSON playlist: {playlist}")
            return playlist
            
        except Exception as e:
            raise ValueError(f"Failed to parse JSON playlist {playlist_path}: {e}")
    
    
    def load_playlist(self, playlist_path: Path) -> Playlist:
        """
        Load a playlist from JSON format.
        
        Args:
            playlist_path: Path to the JSON playlist file
            
        Returns:
            Playlist object
            
        Raises:
            ValueError: If the file format is unsupported or parsing fails
        """
        if not playlist_path.exists():
            raise ValueError(f"Playlist file not found: {playlist_path}")
        
        if playlist_path.suffix.lower() == ".json":
            return self.parse_json_playlist(playlist_path)
        else:
            raise ValueError(f"Unsupported playlist format: {playlist_path.suffix}. Only JSON format is supported.")
    
    def search_playlist(self, 
                       playlist: Playlist, 
                       config: Optional[RecotineConfig] = None,
                       download: bool = True) -> Dict[str, List[Track]]:
        """
        Search for all tracks in a playlist and optionally download them.
        
        Args:
            playlist: Playlist object containing tracks to search for
            config: RecotineConfig instance (optional)
            download: Whether to download found tracks (default: True)
            
        Returns:
            Dictionary with 'found' and 'not_found' lists of tracks
        """
        if config is None:
            config = load_config()
        
        # Check API availability if downloading
        if download and not self.track_searcher.api.is_available():
            raise NicotineAPIError("Nicotine++ API is not available")
        
        results = {"found": [], "not_found": []}
        
        print(f"\n🎵 Processing playlist: {playlist.title}")
        print(f"👤 Creator: {playlist.creator}")
        print(f"🎶 Total tracks: {len(playlist.tracks)}")
        if download:
            playlist_dir = self.output_dir / playlist.title
            playlist_dir.mkdir(parents=True, exist_ok=True)
            print(f"📁 Output directory: {playlist_dir}")
        print("-" * 60)
        
        for i, track in enumerate(playlist.tracks, 1):
            print(f"[{i:2d}/{len(playlist.tracks)}] {track}")
            
            try:
                # Search for the track
                search_results = self.track_searcher.search_track(track, config)
                
                if search_results:
                    results["found"].append(track)
                    best_result = search_results[0]  # Already sorted by similarity
                    
                    if download:
                        try:
                            download_response = self.track_searcher.api.download_best_result(
                                search_results,
                                prefer_free_slots=config.npp_search_require_free_slots,
                                min_bitrate=config.npp_search_min_bitrate
                            )
                            print(f"         ✅ Queued: {best_result.file_name} ({best_result.bitrate or 'Unknown'} kbps)")
                            self.stats["successful_downloads"] += 1
                        except Exception as e:
                            print(f"         ❌ Download failed: {e}")
                            self.stats["api_errors"] += 1
                    else:
                        print(f"         ✅ Found: {best_result.file_name} ({best_result.bitrate or 'Unknown'} kbps)")
                else:
                    results["not_found"].append(track)
                    print(f"         ❌ No suitable results found")
                    self.stats["failed_searches"] += 1
                
            except Exception as e:
                results["not_found"].append(track)
                print(f"         ❌ Search error: {e}")
                self.stats["api_errors"] += 1
            
            self.stats["total_tracks"] += 1
            
            # Small delay between searches to be respectful
            if i < len(playlist.tracks):  # Don't delay after the last track
                time.sleep(1)
        
        # Print summary
        found_count = len(results["found"])
        not_found_count = len(results["not_found"])
        success_rate = (found_count / len(playlist.tracks) * 100) if playlist.tracks else 0
        
        print(f"\n📊 Playlist '{playlist.title}' processing complete:")
        print(f"    ✅ Found: {found_count}")
        print(f"    ❌ Not found: {not_found_count}")
        print(f"    📈 Success rate: {success_rate:.1f}%")
        
        # Output information about tracks that were not found
        if results["not_found"]:
            print(f"\n❌ Tracks that could not be found:")
            for track in results["not_found"]:
                print(f"    - {track}")
        
        return results
    
    def search_playlist_file(self, 
                            playlist_path: Path, 
                            config: Optional[RecotineConfig] = None,
                            download: bool = True) -> Dict[str, List[Track]]:
        """
        Search for tracks in a playlist file.
        
        Args:
            playlist_path: Path to the playlist file
            config: RecotineConfig instance (optional)
            download: Whether to download found tracks (default: True)
            
        Returns:
            Dictionary with 'found' and 'not_found' lists of tracks
        """
        playlist = self.load_playlist(playlist_path)
        return self.search_playlist(playlist, config, download)
    
    def get_available_playlists(self, search_dir: Path = None) -> List[Path]:
        """
        Get list of available JSON playlist files in the search directory.
        
        Args:
            search_dir: Directory to search for playlists (defaults to ./recs/)
            
        Returns:
            List of JSON playlist file paths
        """
        if search_dir is None:
            search_dir = OUTPUT_DIR
        
        if not search_dir.exists():
            return []
        
        # Search for JSON playlist files only
        playlist_files = list(search_dir.rglob("*.json"))
        
        return sorted(playlist_files)
    
    def search_all_playlists(self, 
                            search_dir: Path = None, 
                            config: Optional[RecotineConfig] = None,
                            download: bool = True) -> None:
        """
        Search for tracks in all available playlists.
        
        Args:
            search_dir: Directory to search for playlists (defaults to ./recs/)
            config: RecotineConfig instance (optional)
            download: Whether to download found tracks (default: True)
        """
        playlists = self.get_available_playlists(search_dir)
        
        if not playlists:
            print("❌ No playlist files found")
            return
        
        print(f"🎵 Found {len(playlists)} playlists:")
        for playlist in playlists:
            print(f"    - {playlist.name}")
        print()
        
        all_results = {"found": [], "not_found": []}
        
        for playlist_path in playlists:
            try:
                results = self.search_playlist_file(playlist_path, config, download)
                all_results["found"].extend(results["found"])
                all_results["not_found"].extend(results["not_found"])
                print()  # Extra spacing between playlists
            except KeyboardInterrupt:
                print("\n⏹️ Search interrupted by user")
                break
            except Exception as e:
                logger.error(f"Error processing playlist {playlist_path}: {e}")
                print(f"❌ Error processing {playlist_path.name}: {e}")
                continue
        
        self.print_final_summary()
    
    def print_final_summary(self) -> None:
        """Print final statistics summary."""
        print("=" * 60)
        print("🎵 FINAL SUMMARY")
        print("=" * 60)
        print(f"📊 Total tracks processed: {self.stats['total_tracks']}")
        print(f"✅ Successful downloads: {self.stats['successful_downloads']}")
        print(f"❌ Failed searches: {self.stats['failed_searches']}")
        print(f"⚠️  API errors: {self.stats['api_errors']}")
        
        if self.stats["total_tracks"] > 0:
            success_rate = (self.stats["successful_downloads"] / self.stats["total_tracks"] * 100)
            print(f"📈 Overall success rate: {success_rate:.1f}%")
        print("=" * 60)


# Convenience functions for backward compatibility and simple use cases
def search_track(track: Track, 
                config: Optional[RecotineConfig] = None,
                api_url: str = "http://localhost:7770") -> List[SearchResult]:
    """
    Search for a track using a TrackSearcher instance.
    
    Args:
        track: Track object containing title and artists
        config: RecotineConfig instance (optional)
        api_url: API base URL
        
    Returns:
        List of SearchResult objects matching the track
    """
    searcher = TrackSearcher(api_url)
    return searcher.search_track(track, config)


def download_track(track: Track,
                  config: Optional[RecotineConfig] = None,
                  api_url: str = "http://localhost:7770") -> Optional[str]:
    """
    Search for and download the best result for a track.
    
    Args:
        track: Track object to search for and download
        config: RecotineConfig instance (optional)
        api_url: API base URL
        
    Returns:
        Download response message or None if no suitable results found
    """
    searcher = TrackSearcher(api_url)
    return searcher.download_best_result(track, config)


# Playlist search convenience functions
def search_playlist_file(playlist_path: Path,
                        config: Optional[RecotineConfig] = None,
                        api_url: str = "http://localhost:7770",
                        download: bool = True) -> Dict[str, List[Track]]:
    """
    Search for tracks in a playlist file using a PlaylistSearcher instance.
    
    Args:
        playlist_path: Path to the playlist file
        config: RecotineConfig instance (optional)
        api_url: API base URL
        download: Whether to download found tracks (default: True)
        
    Returns:
        Dictionary with 'found' and 'not_found' lists of tracks
    """
    searcher = PlaylistSearcher(api_url)
    return searcher.search_playlist_file(playlist_path, config, download)


def search_all_playlists(search_dir: Path = None,
                        config: Optional[RecotineConfig] = None,
                        api_url: str = "http://localhost:7770",
                        download: bool = True) -> None:
    """
    Search for tracks in all available playlists using a PlaylistSearcher instance.
    
    Args:
        search_dir: Directory to search for playlists (defaults to ./recs/)
        config: RecotineConfig instance (optional)
        api_url: API base URL
        download: Whether to download found tracks (default: True)
    """
    searcher = PlaylistSearcher(api_url)
    return searcher.search_all_playlists(search_dir, config, download)