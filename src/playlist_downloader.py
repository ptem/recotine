#!/usr/bin/env python3
"""
Playlist Downloader for Nicotine++

This script reads playlist files from the recs/ directory and downloads tracks
using the Nicotine++ Web API. Each song is searched with quoted artist and song
names to find the best match, then downloaded to organized directories.

Usage:
    python playlist_downloader.py                    # Download all playlists
    python playlist_downloader.py playlist_name      # Download specific playlist
    
Requirements:
    - Nicotine++ running with Web API enabled
    - npp_api.py module in the same directory or Python path
    - Playlist files in recs/ directory

Author: Junie
Date: 2025-08-13
"""

import sys
import time
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from npp_api import NicotineAPI, SearchResult, SearchSortBy, NicotineAPIError


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('../playlist_downloader.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class PlaylistEntry:
    """Represents a single track entry from a playlist"""
    
    def __init__(self, artist: str, song: str, original_line: str):
        self.artist = artist.strip()
        self.song = song.strip()
        self.original_line = original_line.strip()
        self.search_query = f'"{self.artist}" "{self.song}"'
    
    def __str__(self):
        return f"{self.artist} - {self.song}"
    
    def __repr__(self):
        return f"PlaylistEntry(artist='{self.artist}', song='{self.song}')"


class PlaylistDownloader:
    """Main class for downloading playlist tracks using Nicotine++ API"""
    
    def __init__(self, api_url: str = "http://localhost:7770"):
        """
        Initialize the playlist downloader
        
        Args:
            api_url: Base URL for the Nicotine++ Web API
        """
        self.api = NicotineAPI(api_url)
        self.recs_dir = Path("../recs")
        self.output_base_dir = Path("output/playlists")
        self.stats = {
            'total_tracks': 0,
            'successful_downloads': 0,
            'failed_searches': 0,
            'api_errors': 0,
            'skipped_tracks': 0
        }
        
        # Ensure output directory exists
        self.output_base_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("Playlist downloader initialized")
    
    def is_api_available(self) -> bool:
        """Check if the Nicotine++ API is available"""
        if not self.api.is_available():
            logger.error("Nicotine++ API is not available")
            print("❌ Nicotine++ API is not available!")
            print("   Make sure Nicotine++ is running with the Web API enabled.")
            return False
        return True
    
    def get_available_playlists(self) -> List[Path]:
        """Get all available playlist files from the recs directory"""
        if not self.recs_dir.exists():
            logger.error(f"Recs directory not found: {self.recs_dir}")
            return []
        
        playlist_files = list(self.recs_dir.glob("*.txt"))
        logger.info(f"Found {len(playlist_files)} playlist files")
        return playlist_files
    
    def parse_playlist_file(self, playlist_path: Path) -> Tuple[str, List[PlaylistEntry]]:
        """
        Parse a playlist file and extract track information
        
        Args:
            playlist_path: Path to the playlist file
            
        Returns:
            Tuple of (playlist_name, list_of_tracks)
        """
        logger.info(f"Parsing playlist: {playlist_path.name}")
        
        tracks = []
        playlist_name = playlist_path.stem  # Filename without extension
        
        try:
            with open(playlist_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue
                    
                    # Parse "Artist - Song" format
                    if ' - ' in line:
                        parts = line.split(' - ', 1)  # Split on first occurrence only
                        if len(parts) == 2:
                            artist, song = parts
                            track = PlaylistEntry(artist, song, line)
                            tracks.append(track)
                        else:
                            logger.warning(f"Could not parse line {line_num}: {line}")
                    else:
                        logger.warning(f"No ' - ' separator found in line {line_num}: {line}")
        
        except Exception as e:
            logger.error(f"Error reading playlist file {playlist_path}: {e}")
            return playlist_name, []
        
        logger.info(f"Parsed {len(tracks)} tracks from {playlist_name}")
        return playlist_name, tracks
    
    def search_and_select_best_track(self, track: PlaylistEntry) -> Optional[SearchResult]:
        """
        Search for a track and select the best result
        
        Args:
            track: PlaylistEntry to search for
            
        Returns:
            Best SearchResult or None if not found
        """
        try:
            logger.info(f"Searching for: {track.search_query}")
            
            # Search with quoted artist and song names
            results = self.api.search_and_filter(
                query=track.search_query,
                min_bitrate=192,  # Prefer decent quality
                require_free_slots=True,  # Prefer users with free slots
                min_similarity=0.3,  # Allow some flexibility in matching
                sort_by=SearchSortBy.BITRATE,  # Prefer higher quality
                limit=10,
                wait_time=8
            )
            
            if not results:
                logger.warning(f"No results found for: {track}")
                return None
            
            # Select the best result (already sorted by bitrate)
            best_result = results[0]
            logger.info(f"Best result: {best_result.file_name} ({best_result.bitrate or 'Unknown'} kbps) from {best_result.user}")
            
            return best_result
            
        except NicotineAPIError as e:
            logger.error(f"API error searching for {track}: {e}")
            self.stats['api_errors'] += 1
            return None
        except Exception as e:
            logger.error(f"Unexpected error searching for {track}: {e}")
            return None
    
    def download_track(self, result: SearchResult, playlist_name: str, track: PlaylistEntry) -> bool:
        """
        Download a track result to the appropriate playlist directory
        
        Args:
            result: SearchResult to download
            playlist_name: Name of the playlist (for directory organization)
            track: Original track entry (for logging)
            
        Returns:
            True if download was initiated successfully, False otherwise
        """
        try:
            # Create playlist-specific directory
            playlist_dir = self.output_base_dir / playlist_name
            playlist_dir.mkdir(exist_ok=True)
            
            logger.info(f"Downloading to {playlist_dir}: {result.file_name}")
            
            # Initiate download
            download_response = self.api.download_search_result(result)
            
            logger.info(f"Download queued: {download_response}")
            return True
            
        except NicotineAPIError as e:
            logger.error(f"API error downloading {track}: {e}")
            self.stats['api_errors'] += 1
            return False
        except Exception as e:
            logger.error(f"Unexpected error downloading {track}: {e}")
            return False
    
    def download_playlist(self, playlist_path: Path) -> Dict[str, int]:
        """
        Download all tracks from a single playlist
        
        Args:
            playlist_path: Path to the playlist file
            
        Returns:
            Dictionary with download statistics
        """
        playlist_name, tracks = self.parse_playlist_file(playlist_path)
        
        if not tracks:
            logger.warning(f"No tracks found in playlist: {playlist_name}")
            return {'total': 0, 'successful': 0, 'failed': 0}
        
        print(f"\n🎵 Downloading playlist: {playlist_name}")
        print(f"📁 Output directory: output/playlists/{playlist_name}/")
        print(f"🎶 Total tracks: {len(tracks)}")
        print("-" * 60)
        
        playlist_stats = {'total': len(tracks), 'successful': 0, 'failed': 0}
        
        for i, track in enumerate(tracks, 1):
            print(f"[{i:2d}/{len(tracks)}] {track}")
            
            # Search for the best result
            best_result = self.search_and_select_best_track(track)
            
            if best_result:
                # Attempt to download
                if self.download_track(best_result, playlist_name, track):
                    print(f"         ✅ Queued: {best_result.file_name} ({best_result.bitrate or 'Unknown'} kbps)")
                    playlist_stats['successful'] += 1
                    self.stats['successful_downloads'] += 1
                else:
                    print(f"         ❌ Download failed")
                    playlist_stats['failed'] += 1
            else:
                print(f"         ❌ No suitable results found")
                playlist_stats['failed'] += 1
                self.stats['failed_searches'] += 1
            
            self.stats['total_tracks'] += 1
            
            # Small delay between searches to be respectful
            time.sleep(1)
        
        print(f"\n📊 Playlist {playlist_name} complete:")
        print(f"    ✅ Successful: {playlist_stats['successful']}")
        print(f"    ❌ Failed: {playlist_stats['failed']}")
        print(f"    📈 Success rate: {(playlist_stats['successful']/playlist_stats['total']*100):.1f}%")
        
        return playlist_stats
    
    def download_all_playlists(self) -> None:
        """Download all available playlists"""
        playlists = self.get_available_playlists()
        
        if not playlists:
            print("❌ No playlist files found in recs/ directory")
            return
        
        print(f"🎵 Found {len(playlists)} playlists to download:")
        for playlist in playlists:
            print(f"    - {playlist.name}")
        print()
        
        for playlist_path in playlists:
            try:
                self.download_playlist(playlist_path)
                print()  # Extra spacing between playlists
            except KeyboardInterrupt:
                print("\n⏹️ Download interrupted by user")
                break
            except Exception as e:
                logger.error(f"Error processing playlist {playlist_path}: {e}")
                print(f"❌ Error processing {playlist_path.name}: {e}")
                continue
        
        self.print_final_summary()
    
    def download_specific_playlist(self, playlist_name: str) -> None:
        """
        Download a specific playlist by name
        
        Args:
            playlist_name: Name of the playlist to download (without .txt extension)
        """
        # Try to find the playlist file
        possible_paths = [
            self.recs_dir / f"{playlist_name}.txt",
            self.recs_dir / playlist_name  # In case full filename provided
        ]
        
        playlist_path = None
        for path in possible_paths:
            if path.exists():
                playlist_path = path
                break
        
        if not playlist_path:
            print(f"❌ Playlist not found: {playlist_name}")
            print(f"Available playlists:")
            for p in self.get_available_playlists():
                print(f"    - {p.stem}")
            return
        
        self.download_playlist(playlist_path)
        self.print_final_summary()
    
    def print_final_summary(self) -> None:
        """Print final download statistics"""
        total = self.stats['total_tracks']
        successful = self.stats['successful_downloads']
        
        print("=" * 60)
        print("🎵 DOWNLOAD SUMMARY")
        print("=" * 60)
        print(f"Total tracks processed: {total}")
        print(f"Successful downloads:   {successful}")
        print(f"Failed searches:        {self.stats['failed_searches']}")
        print(f"API errors:             {self.stats['api_errors']}")
        if total > 0:
            print(f"Success rate:           {(successful/total*100):.1f}%")
        print(f"Output directory:       {self.output_base_dir.absolute()}")
        print()
        print("💡 Tip: Check your Nicotine++ downloads tab to monitor progress")
        print("💡 Tip: Run 'python npp_api.py' to check API status and manage downloads")


def main():
    """Main function"""
    print("🎵 Playlist Downloader for Nicotine++")
    print("=" * 50)
    
    # Initialize downloader
    downloader = PlaylistDownloader()
    
    # Check API availability
    if not downloader.is_api_available():
        sys.exit(1)
    
    print("✅ Nicotine++ API is available!")
    
    # Determine what to download based on command line arguments
    if len(sys.argv) > 1:
        playlist_name = sys.argv[1]
        print(f"📂 Downloading specific playlist: {playlist_name}")
        downloader.download_specific_playlist(playlist_name)
    else:
        print("📂 Downloading all available playlists")
        downloader.download_all_playlists()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹️ Download interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)