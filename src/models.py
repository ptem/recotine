"""Unified data structures for playlists and tracks.

This module provides standardized classes for handling playlist and track data
from different sources (e.g., Last.fm, ListenBrainz) in a consistent format.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import json


@dataclass
class Links:
    """Links associated with a playlist or track."""
    mbid: Optional[str] = None
    url: Optional[str] = None


@dataclass
class Track:
    """Unified track structure for all music sources."""
    title: str
    artists: List[str] = field(default_factory=list)
    links: Links = field(default_factory=Links)
    
    def __str__(self) -> str:
        """String representation of the track."""
        artist_str = ", ".join(self.artists) if self.artists else "Unknown Artist"
        return f"{artist_str} - {self.title}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert track to dictionary representation."""
        return {
            "title": self.title,
            "artists": self.artists,
            "links": {
                "mbid": self.links.mbid,
                "url": self.links.url
            }
        }

@dataclass
class Playlist:
    """Unified playlist structure for all music sources."""
    title: str
    creator: str
    links: Links = field(default_factory=Links)
    tracks: List[Track] = field(default_factory=list)
    
    def __str__(self) -> str:
        """String representation of the playlist."""
        return f"{self.title} by {self.creator} ({len(self.tracks)} tracks)"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert playlist to dictionary representation."""
        return {
            "title": self.title,
            "creator": self.creator,
            "links": {
                "mbid": self.links.mbid,
                "url": self.links.url
            },
            "tracks": [track.to_dict() for track in self.tracks]
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Convert playlist to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
    
    def save_to_json(self, filename: Optional[str] = None) -> Path:
        """Save playlist to JSON file.

        Args:
            filename: Optional filename.

        Returns:
            Path to the saved JSON file
        """
        date_str = datetime.now().strftime("%Y-%m-%d")

        if filename is None:
            filename = f"{self.title.lower().replace(' ','_').replace('.','')}.json"

        file_path = Path("../recs") / Path(date_str) / filename
        file_path.parent.mkdir(exist_ok=True)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(self.to_json())
            print(f"Saved playlist JSON '{self.title}' to {file_path}")

        return file_path
    