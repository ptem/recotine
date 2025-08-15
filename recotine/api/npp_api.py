#!/usr/bin/env python3
"""
Nicotine++ Web API Python Wrapper

This module provides a convenient Python interface for the Nicotine++ Web API,
making it easy to search for files and manage downloads programmatically.

Example usage:
    from npp_api import NicotineAPI
    
    api = NicotineAPI()
    if api.is_available():
        results = api.search("Pink Floyd", min_bitrate=320)
        if results:
            api.download_best_result(results)

Author: Junie
Date: 2025-08-12
"""

import logging
import sys
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any

import requests

from recotine.paths import PROJECT_ROOT
from recotine.cfg.config import RecotineConfig

# Add current directory to path to import modules
sys.path.append(str(PROJECT_ROOT / "recotine"))


def _get_default_api_url() -> str:
    """Get the default API URL from configuration, fallback to hardcoded default."""
    try:
        config = RecotineConfig()
        host = config.npp_api_host
        port = config.npp_api_port
        return f"http://{host}:{port}"
    except Exception:
        # Fallback to hardcoded default if config loading fails
        return "http://localhost:7770"


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SearchSortBy(Enum):
    """Enumeration for search result sorting options"""
    BITRATE = "bitrate"
    FILE_SIZE = "file_size" 
    SIMILARITY = "search_similarity"
    USER = "user"
    FILE_NAME = "file_name"


@dataclass
class SearchResult:
    """Represents a single search result with convenient property access"""
    user: str
    ip_address: str
    port: int
    has_free_slots: bool
    inqueue: int
    ulspeed: int
    file_name: str
    file_extension: str
    file_path: str
    file_size: int
    file_h_length: str
    bitrate: Optional[int]
    search_similarity: float
    file_attributes: Optional[Dict] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SearchResult":
        """Create SearchResult from API response dictionary"""
        return cls(
            user=data.get("user", ""),
            ip_address=data.get("ip_address", ""),
            port=data.get("port", 0),
            has_free_slots=data.get("has_free_slots", False),
            inqueue=data.get("inqueue", 0),
            ulspeed=data.get("ulspeed", 0),
            file_name=data.get("file_name", ""),
            file_extension=data.get("file_extension", ""),
            file_path=data.get("file_path", ""),
            file_size=data.get("file_size", 0),
            file_h_length=data.get("file_h_length", ""),
            bitrate=data.get("bitrate"),
            search_similarity=data.get("search_similarity", 0.0),
            file_attributes=data.get("file_attributes")
        )
    
    @property
    def file_size_mb(self) -> float:
        """Get file size in megabytes"""
        return self.file_size / (1024 * 1024)
    
    @property
    def is_high_quality(self) -> bool:
        """Check if this is a high quality audio file (320+ kbps)"""
        return self.bitrate is not None and self.bitrate >= 320
    
    def __str__(self) -> str:
        return f'{self.file_name} - {self.user} ({self.bitrate or "Unknown"} kbps)'


@dataclass 
class DownloadInfo:
    """Represents information about a download"""
    username: str
    virtual_path: str
    download_path: str
    status: str
    size: int
    current_byte_offset: Optional[int]
    download_percentage: Optional[str]
    file_attributes: Optional[Dict] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DownloadInfo":
        """Create DownloadInfo from API response dictionary"""
        return cls(
            username=data.get("username", ""),
            virtual_path=data.get("virtual_path", ""),
            download_path=data.get("download_path", ""),
            status=data.get("status", ""),
            size=data.get("size", 0),
            current_byte_offset=data.get("current_byte_offset"),
            download_percentage=data.get("download_percentage"),
            file_attributes=data.get("file_attributes")
        )
    
    @property
    def size_mb(self) -> float:
        """Get file size in megabytes"""
        return self.size / (1024 * 1024)
    
    @property
    def progress_percent(self) -> float:
        """Get download progress as a float percentage (0-100)"""
        if self.current_byte_offset is None or self.size == 0:
            return 0.0
        return (self.current_byte_offset * 100.0) / self.size


class NicotineAPIError(Exception):
    """Custom exception for Nicotine++ API errors"""
    pass


class NicotineAPI:
    """
    Python wrapper for the Nicotine++ Web API
    
    This class provides convenient methods for searching files and managing downloads
    through the Nicotine++ Web API.
    """
    
    def __init__(self, base_url: Optional[str] = None, timeout: int = 30):
        """
        Initialize the API wrapper

        Args:
            base_url: Base URL of the Nicotine++ Web API (if None, uses configuration)
            timeout: Request timeout in seconds
        """
        if base_url is None:
            base_url = _get_default_api_url()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.timeout = timeout

        logger.info(f"Initialized NicotineAPI with base URL: {self.base_url}")

    def is_available(self) -> bool:
        """
        Check if the Nicotine++ Web API is available and responding

        Returns:
            True if API is available, False otherwise
        """
        try:
            response = self.session.get(f"{self.base_url}/foo")
            is_available = response.status_code == 200 and response.json().get("message") == "Hello World"
            logger.info(f'API availability check: {"Available" if is_available else "Unavailable"}')
            return is_available
        except requests.exceptions.RequestException as e:
            logger.warning(f"API availability check failed: {e}")
            return False

    def search(self, 
               query: str, 
               wait_time: int = 10, 
               min_bitrate: Optional[int] = None,
               require_free_slots: bool = False,
               search_filters: Optional[Dict[str, Any]] = None,
               smart_filters: Optional[bool] = None,
               includes_text: Optional[List[str]] = None,
               excludes_text: Optional[List[str]] = None) -> List[SearchResult]:
        """
        Perform a global search across the Soulseek network
        
        Args:
            query: Search term/query
            wait_time: How long to wait for results (seconds)
            min_bitrate: Minimum bitrate for audio files
            require_free_slots: Only return results from users with free upload slots
            search_filters: Additional search filters dictionary
            smart_filters: Enable intelligent filtering
            includes_text: List of strings that must all be present in file name or path
            excludes_text: List of strings that will exclude results if any are found in file name or path
            
        Returns:
            List of SearchResult objects
            
        Raises:
            NicotineAPIError: If search fails or API returns error
        """
        logger.info(f"Performing search: '{query}' (wait_time={wait_time})")
        
        search_data = {
            "search_term": query,
            "wait_for_seconds": wait_time
        }
        
        # Build search filters
        filters = search_filters.copy() if search_filters else {}
        if min_bitrate is not None:
            filters["min_bitrate"] = min_bitrate
        if require_free_slots:
            filters["require_free_slots"] = require_free_slots
            
        if filters:
            search_data["search_filters"] = filters
            
        if smart_filters is not None:
            search_data["smart_filters"] = smart_filters
        
        try:
            response = self.session.get(f"{self.base_url}/search/global", json=search_data)
            response.raise_for_status()
            
            results_data = response.json()
            
            # Handle various response types
            if isinstance(results_data, str):
                logger.warning(f"Search returned message: {results_data}")
                if "Too many simultaneous searches" in results_data:
                    raise NicotineAPIError("Too many simultaneous searches. Please try again later.")
                elif "No results found" in results_data:
                    return []
                else:
                    raise NicotineAPIError(f"Search failed: {results_data}")
            
            elif isinstance(results_data, list):
                search_results = [SearchResult.from_dict(item) for item in results_data]
                
                # Apply includes_text filtering if provided
                if includes_text:
                    filtered_results = []
                    for result in search_results:
                        # Check if all strings in includes_text are present in file name or path (case-insensitive)
                        search_text = f"{result.file_name} {result.file_path}".lower()
                        if all(text.lower() in search_text for text in includes_text):
                            filtered_results.append(result)
                    search_results = filtered_results
                    logger.info(f"Applied includes_text filter: {len(search_results)} results remaining")
                
                # Apply excludes_text filtering if provided
                if excludes_text:
                    filtered_results = []
                    for result in search_results:
                        # Check if any strings in excludes_text are present in file name or path (case-insensitive)
                        search_text = f"{result.file_name} {result.file_path}".lower()
                        if not any(text.lower() in search_text for text in excludes_text):
                            filtered_results.append(result)
                    search_results = filtered_results
                    logger.info(f"Applied excludes_text filter: {len(search_results)} results remaining")
                
                logger.info(f"Search completed: {len(search_results)} results found")
                return search_results
                
            elif isinstance(results_data, dict):
                # Handle search_req object response
                if 'results' in results_data and isinstance(results_data['results'], list):
                    # Convert Pydantic model objects to dictionaries if needed
                    results_list = []
                    for item in results_data['results']:
                        if isinstance(item, dict):
                            results_list.append(item)
                        else:
                            # Handle Pydantic model objects
                            try:
                                if hasattr(item, 'model_dump'):
                                    results_list.append(item.model_dump())
                                elif hasattr(item, 'dict'):
                                    results_list.append(item.dict())
                                else:
                                    # Try to convert object attributes to dict
                                    item_dict = {}
                                    for attr in ['user', 'ip_address', 'port', 'has_free_slots', 'inqueue', 'ulspeed', 
                                                'file_name', 'file_extension', 'file_path', 'file_size', 'file_h_length', 
                                                'bitrate', 'search_similarity', 'file_attributes']:
                                        if hasattr(item, attr):
                                            item_dict[attr] = getattr(item, attr)
                                    results_list.append(item_dict)
                            except Exception as e:
                                logger.warning(f"Failed to convert result item: {e}")
                                continue
                    
                    search_results = [SearchResult.from_dict(item) for item in results_list]
                    
                    # Apply includes_text filtering if provided
                    if includes_text:
                        filtered_results = []
                        for result in search_results:
                            # Check if all strings in includes_text are present in file name or path (case-insensitive)
                            search_text = f"{result.file_name} {result.file_path}".lower()
                            if all(text.lower() in search_text for text in includes_text):
                                filtered_results.append(result)
                        search_results = filtered_results
                        logger.info(f"Applied includes_text filter: {len(search_results)} results remaining")
                    
                    # Apply excludes_text filtering if provided
                    if excludes_text:
                        filtered_results = []
                        for result in search_results:
                            # Check if any strings in excludes_text are present in file name or path (case-insensitive)
                            search_text = f"{result.file_name} {result.file_path}".lower()
                            if not any(text.lower() in search_text for text in excludes_text):
                                filtered_results.append(result)
                        search_results = filtered_results
                        logger.info(f"Applied excludes_text filter: {len(search_results)} results remaining")
                    
                    logger.info(f"Search completed: {len(search_results)} results found")
                    return search_results
                else:
                    logger.warning(f"Dictionary response missing 'results' key or results not a list: {results_data.keys() if isinstance(results_data, dict) else 'Unknown'}")
                    return []
                
            else:
                logger.warning(f"Unexpected search response format: {type(results_data)}")
                return []
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Search request failed: {e}")
            raise NicotineAPIError(f"Search request failed: {e}")
    
    def search_and_filter(self,
                         query: str,
                         min_bitrate: Optional[int] = None,
                         max_file_size_mb: Optional[float] = None,
                         min_similarity: float = 0.0,
                         require_free_slots: bool = False,
                         file_extensions: Optional[List[str]] = None,
                         sort_by: SearchSortBy = SearchSortBy.SIMILARITY,
                         limit: Optional[int] = None,
                         wait_time: int = 10,
                         includes_text: Optional[List[str]] = None,
                         excludes_text: Optional[List[str]] = None) -> List[SearchResult]:
        """
        Advanced search with client-side filtering and sorting
        
        Args:
            query: Search term
            min_bitrate: Minimum audio bitrate
            max_file_size_mb: Maximum file size in MB
            min_similarity: Minimum similarity score (0-1)
            require_free_slots: Only users with free slots
            file_extensions: List of allowed file extensions (e.g., ['mp3', 'flac'])
            sort_by: How to sort results
            limit: Maximum number of results to return
            wait_time: Search wait time in seconds
            includes_text: List of strings that must all be present in file name or path
            excludes_text: List of strings that will exclude results if any are found in file name or path
            
        Returns:
            Filtered and sorted list of SearchResult objects
        """
        # Perform the search
        results = self.search(
            query=query,
            wait_time=wait_time,
            min_bitrate=min_bitrate,
            require_free_slots=require_free_slots,
            includes_text=includes_text,
            excludes_text=excludes_text
        )
        
        # Apply client-side filters
        filtered_results = []
        for result in results:
            # Bitrate filter (client-side backup in case server-side filtering fails)
            if min_bitrate is not None and result.bitrate is not None and result.bitrate < min_bitrate:
                continue
                
            # Free slots filter (client-side backup in case server-side filtering fails)
            if require_free_slots and not result.has_free_slots:
                continue
                
            # File size filter
            if max_file_size_mb and result.file_size_mb > max_file_size_mb:
                continue
                
            # Similarity filter
            if result.search_similarity < min_similarity:
                continue
                
            # File extension filter
            if file_extensions and result.file_extension.lower() not in [ext.lower() for ext in file_extensions]:
                continue
                
            filtered_results.append(result)
        
        # Sort results
        if sort_by == SearchSortBy.BITRATE:
            filtered_results.sort(key=lambda x: x.bitrate or 0, reverse=True)
        elif sort_by == SearchSortBy.FILE_SIZE:
            filtered_results.sort(key=lambda x: x.file_size, reverse=True)
        elif sort_by == SearchSortBy.SIMILARITY:
            filtered_results.sort(key=lambda x: x.search_similarity, reverse=True)
        elif sort_by == SearchSortBy.USER:
            filtered_results.sort(key=lambda x: x.user)
        elif sort_by == SearchSortBy.FILE_NAME:
            filtered_results.sort(key=lambda x: x.file_name)
        
        # Apply limit
        if limit:
            filtered_results = filtered_results[:limit]
            
        logger.info(f"Filtered search results: {len(filtered_results)} results after filtering")
        return filtered_results
    
    def download(self, 
                 user: str, 
                 virtual_path: str, 
                 file_size: int, 
                 file_attributes: Optional[Dict] = None) -> str:
        """
        Download a file from a user
        
        Args:
            user: Username of the file owner
            virtual_path: Virtual path to the file
            file_size: File size in bytes
            file_attributes: Optional file metadata
            
        Returns:
            Response message from API
            
        Raises:
            NicotineAPIError: If download request fails
        """
        logger.info(f"Downloading file: {virtual_path} from {user}")
        
        download_data = {
            "file_owner": user,
            "file_virtual_path": virtual_path,
            "file_size": file_size
        }
        
        if file_attributes:
            download_data["file_attributes"] = file_attributes
        
        try:
            response = self.session.get(f"{self.base_url}/download", json=download_data)
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"Download enqueued successfully: {result}")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Download request failed: {e}")
            raise NicotineAPIError(f"Download request failed: {e}")
    
    def download_search_result(self, result: SearchResult) -> str:
        """
        Convenience method to download a SearchResult object
        
        Args:
            result: SearchResult to download
            
        Returns:
            Response message from API
        """
        return self.download(
            user=result.user,
            virtual_path=result.file_path,
            file_size=result.file_size,
            file_attributes=result.file_attributes
        )
    
    def download_best_result(self, 
                           results: List[SearchResult], 
                           prefer_free_slots: bool = True,
                           min_bitrate: Optional[int] = None) -> Optional[str]:
        """
        Download the best result from a list based on quality and availability
        
        Args:
            results: List of search results
            prefer_free_slots: Prefer users with free upload slots
            min_bitrate: Minimum acceptable bitrate
            
        Returns:
            Download response message, or None if no suitable result found
        """
        if not results:
            logger.warning("No results provided for download")
            return None
        
        # Filter results
        filtered_results = results[:]
        
        if min_bitrate:
            filtered_results = [r for r in filtered_results if r.bitrate and r.bitrate >= min_bitrate]
        
        if prefer_free_slots:
            free_slot_results = [r for r in filtered_results if r.has_free_slots]
            if free_slot_results:
                filtered_results = free_slot_results
        
        if not filtered_results:
            logger.warning("No suitable results found for download after filtering")
            return None
        
        # Sort by bitrate (highest first), then by similarity
        best_result = max(filtered_results, key=lambda x: (x.bitrate or 0, x.search_similarity))
        
        logger.info(f"Selected best result: {best_result}")
        return self.download_search_result(best_result)
    
    def get_downloads(self) -> List[DownloadInfo]:
        """
        Get all current downloads
        
        Returns:
            List of DownloadInfo objects
            
        Raises:
            NicotineAPIError: If request fails
        """
        try:
            response = self.session.get(f"{self.base_url}/download/getdownloads")
            response.raise_for_status()
            
            downloads_data = response.json()
            downloads = [DownloadInfo.from_dict(item) for item in downloads_data]
            
            logger.info(f"Retrieved {len(downloads)} downloads")
            return downloads
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Get downloads request failed: {e}")
            raise NicotineAPIError(f"Get downloads request failed: {e}")
    
    def get_active_downloads(self) -> List[DownloadInfo]:
        """
        Get only active/in-progress downloads
        
        Returns:
            List of active DownloadInfo objects
        """
        all_downloads = self.get_downloads()
        active_downloads = [dl for dl in all_downloads if dl.status not in ['Finished', 'Cancelled', 'Failed']]
        logger.info(f"Found {len(active_downloads)} active downloads")
        return active_downloads
    
    def clean_downloads(self) -> str:
        """
        Clean up finished and cancelled downloads
        
        Returns:
            Response message from API
            
        Raises:
            NicotineAPIError: If request fails
        """
        logger.info("Cleaning up downloads")
        
        try:
            response = self.session.delete(f"{self.base_url}/download/abortandclean")
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"Downloads cleaned: {result}")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Clean downloads request failed: {e}")
            raise NicotineAPIError(f"Clean downloads request failed: {e}")
    
    def wait_for_downloads(self, 
                          timeout: int = 300, 
                          check_interval: int = 5,
                          cleanup_when_done: bool = True) -> List[DownloadInfo]:
        """
        Wait for all active downloads to complete
        
        Args:
            timeout: Maximum time to wait in seconds
            check_interval: How often to check progress in seconds
            cleanup_when_done: Whether to clean up downloads when done
            
        Returns:
            Final list of download statuses
        """
        logger.info(f"Waiting for downloads to complete (timeout={timeout}s)")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            active_downloads = self.get_active_downloads()
            
            if not active_downloads:
                logger.info("All downloads completed")
                break
                
            logger.info(f"Waiting for {len(active_downloads)} downloads to complete...")
            for dl in active_downloads:
                logger.info(f"  {dl.virtual_path}: {dl.download_percentage or '0%'}")
                
            time.sleep(check_interval)
        else:
            logger.warning(f"Timeout reached after {timeout} seconds")
        
        final_downloads = self.get_downloads()
        
        if cleanup_when_done:
            self.clean_downloads()
            
        return final_downloads



# Convenience functions
def quick_search(query: str, 
                min_bitrate: int = 192, 
                limit: int = 10,
                api_url: Optional[str] = None) -> List[SearchResult]:
    """
    Quick search function for simple use cases
    
    Args:
        query: Search term
        min_bitrate: Minimum bitrate for audio files
        limit: Maximum number of results
        api_url: API base URL (if None, uses configuration)
        
    Returns:
        List of search results
    """
    if api_url is None:
        api_url = _get_default_api_url()
    api = NicotineAPI(api_url)
    
    if not api.is_available():
        raise NicotineAPIError("Nicotine++ API is not available")
    
    return api.search_and_filter(
        query=query,
        min_bitrate=min_bitrate,
        sort_by=SearchSortBy.BITRATE,
        limit=limit
    )


def auto_download(query: str,
                 min_bitrate: int = 320,
                 prefer_free_slots: bool = True,
                 api_url: Optional[str] = None) -> Optional[str]:
    """
    Automatically search and download the best result
    
    Args:
        query: Search term
        min_bitrate: Minimum acceptable bitrate
        prefer_free_slots: Prefer users with free upload slots
        api_url: API base URL (if None, uses configuration)
        
    Returns:
        Download response message or None
    """
    if api_url is None:
        api_url = _get_default_api_url()
    api = NicotineAPI(api_url)
    
    if not api.is_available():
        raise NicotineAPIError("Nicotine++ API is not available")
    
    results = api.search_and_filter(
        query=query,
        min_bitrate=min_bitrate,
        require_free_slots=prefer_free_slots,
        sort_by=SearchSortBy.BITRATE,
        limit=20
    )
    
    if results:
        return api.download_best_result(results, prefer_free_slots=prefer_free_slots, min_bitrate=min_bitrate)
    else:
        logger.warning(f"No suitable results found for: {query}")
        return None


# Example usage and testing
if __name__ == "__main__":
    # Example usage
    api = NicotineAPI()
    
    try:
        # Check API availability
        if not api.is_available():
            print("❌ Nicotine++ API is not available. Make sure it's running with Web API enabled.")
            exit(1)
        
        print("✅ Nicotine++ API is available!")
        
        # Perform a search
        print("\n🔍 Searching for music...")
        results = api.search_and_filter(
            query="Pink Floyd Dark Side",
            min_bitrate=192,
            require_free_slots=True,
            sort_by=SearchSortBy.BITRATE,
            limit=5
        )
        
        if results:
            print(f"\n📁 Found {len(results)} high-quality results:")
            for i, result in enumerate(results, 1):
                print(f"  {i}. {result.file_name}")
                print(f"     User: {result.user} | Bitrate: {result.bitrate or 'Unknown'} kbps")
                print(f"     Size: {result.file_size_mb:.1f} MB | Similarity: {result.search_similarity:.2f}")
                print(f"     Free slots: {'Yes' if result.has_free_slots else 'No'}")
                print()
            
            # Download the best result
            print("⬇️ Downloading best result...")
            download_response = api.download_best_result(results)
            print(f"Download response: {download_response}")
            
        else:
            print("❌ No results found")
            
        # Check current downloads
        print("\n📥 Current downloads:")
        downloads = api.get_downloads()
        if downloads:
            for dl in downloads:
                print(f"  {dl.virtual_path}: {dl.download_percentage or '0%'} ({dl.status})")
        else:
            print("  No active downloads")
            
    except NicotineAPIError as e:
        print(f"❌ API Error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")