"""Track search functionality utilizing npp_api, models, and config.

This module provides track-specific search and download functionality that builds
upon the core NPP API but is not strictly part of the API itself.
"""

import logging
from typing import Optional, List
from pathlib import Path
import sys

# Add current directory to path to import config and models
sys.path.append(str(Path(__file__).parent))
from config import load_config, RecotineConfig
from models import Track
from npp_api import NicotineAPI, SearchResult, SearchSortBy, NicotineAPIError

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