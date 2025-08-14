"""Configuration management for Recotine."""

from pathlib import Path
from typing import Dict, Any, Optional

import yaml

from recotine.paths import CONFIG_DIR, PROJECT_ROOT


class RecotineConfig:
    """Handles loading and validation of Recotine configuration."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration loader.
        
        Args:
            config_path: Path to recotine.yaml file. Defaults to config/recotine.yaml, then ./recotine.yaml
        """
        if config_path is None:
            # First try config/recotine.yaml, then fall back to ./recotine.yaml
            config_in_config_dir = CONFIG_DIR / "recotine.yaml"
            config_in_root = CONFIG_DIR.parent / "recotine.yaml"
            
            if config_in_config_dir.exists():
                config_path = config_in_config_dir
            else:
                config_path = config_in_root
        else:
            config_path = Path(config_path)
            
        self.config_path = config_path
        self._config: Dict[str, Any] = {}
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_path.name}\n"
                f"Please copy config/recotine.yaml.template to config/recotine.yaml "
                f"and fill in your credentials."
            )
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in configuration file: {e}")
    
    def _get_nested(self, keys: str, default: Any = None) -> Any:
        """Get nested configuration value using dot notation."""
        value = self._config
        for key in keys.split('.'):
            if not isinstance(value, dict) or key not in value:
                return default
            value = value[key]
        return value
    
    # Last.fm configuration properties
    @property
    def lastfm_username(self) -> str:
        """Get Last.fm username."""
        username = self._get_nested('lastfm.username')
        if not username:
            raise ValueError("Last.fm username not configured")
        return username
    
    @property
    def lastfm_api_key(self) -> str:
        """Get Last.fm API key."""
        api_key = self._get_nested('lastfm.api_key')
        if not api_key:
            raise ValueError("Last.fm API key not configured")
        return api_key
    
    @property
    def lastfm_api_secret(self) -> str:
        """Get Last.fm API secret."""
        api_secret = self._get_nested('lastfm.api_secret')
        if not api_secret:
            raise ValueError("Last.fm API secret not configured")
        return api_secret
    
    @property
    def lastfm_session_key(self) -> Optional[str]:
        """Get Last.fm session key."""
        return self._get_nested('lastfm.session_key')
    
    # ListenBrainz configuration properties
    @property
    def listenbrainz_username(self) -> str:
        """Get ListenBrainz username."""
        username = self._get_nested('listenbrainz.username')
        if not username:
            raise ValueError("ListenBrainz username not configured")
        return username
    
    @property
    def listenbrainz_user_token(self) -> str:
        """Get ListenBrainz user token."""
        token = self._get_nested('listenbrainz.user_token')
        if not token:
            raise ValueError("ListenBrainz user token not configured")
        return token
    
    # Music library configuration
    @property
    def music_library_path(self) -> Path:
        """Get music library path."""
        path = self._get_nested('music.library_path')
        if not path:
            raise ValueError("Music library path not configured")
        return Path(path)
    
    @property
    def music_output_path(self) -> Path:
        """Get music output path."""
        path = self._get_nested('music.output_path')
        if not path:
            raise ValueError("Music output path not configured")
        return Path(path)
    
    # Navidrome configuration (optional)
    @property
    def navidrome_url(self) -> Optional[str]:
        """Get Navidrome server URL."""
        return self._get_nested('navidrome.url')
    
    @property
    def navidrome_username(self) -> Optional[str]:
        """Get Navidrome username."""
        return self._get_nested('navidrome.username')
    
    @property
    def navidrome_password(self) -> Optional[str]:
        """Get Navidrome password."""
        return self._get_nested('navidrome.password')
    
    # Nicotine++ configuration (optional)
    @property
    def npp_network_mode(self) -> str:
        """Get Nicotine++ Docker network mode."""
        return self._get_nested('npp.network_mode', 'host')
    
    @property
    def npp_use_music_library(self) -> bool:
        """Check if Nicotine++ should use music library as shared files directory."""
        return self._get_nested('npp.use_music_library', True)
    
    # Nicotine++ search configuration
    @property
    def npp_search_allowed_extensions(self) -> list:
        """Get allowed file extensions for search."""
        return self._get_nested('npp.search.allowed_extensions', ['mp3', 'flac', 'ogg', 'm4a'])
    
    @property
    def npp_search_min_bitrate(self) -> Optional[int]:
        """Get minimum bitrate requirement."""
        return self._get_nested('npp.search.min_bitrate', 192)
    
    @property
    def npp_search_max_bitrate(self) -> Optional[int]:
        """Get maximum bitrate requirement."""
        return self._get_nested('npp.search.max_bitrate')
    
    @property
    def npp_search_prefer_lossless(self) -> bool:
        """Check if lossless formats should be preferred."""
        return self._get_nested('npp.search.prefer_lossless', False)
    
    @property
    def npp_search_require_free_slots(self) -> bool:
        """Check if free slots are required."""
        return self._get_nested('npp.search.require_free_slots', True)
    
    @property
    def npp_search_max_wait_time(self) -> int:
        """Get maximum wait time for search results."""
        return self._get_nested('npp.search.max_wait_time', 15)
    
    @property
    def npp_search_max_file_size_mb(self) -> Optional[float]:
        """Get maximum file size in MB."""
        return self._get_nested('npp.search.max_file_size_mb', 50)
    
    @property
    def npp_search_min_similarity(self) -> float:
        """Get minimum similarity score requirement."""
        return self._get_nested('npp.search.min_similarity', 0.3)
    
    @property
    def npp_search_sufficient_similarity(self) -> float:
        """Get sufficient similarity score to stop fallback searches."""
        return self._get_nested('npp.search.sufficient_similarity', 0.8)
    
    @property
    def npp_search_max_attempts(self) -> int:
        """Get maximum number of search attempts."""
        return self._get_nested('npp.search.max_search_attempts', 3)
    
    @property
    def npp_search_fallback_strategies(self) -> list:
        """Get fallback search strategies."""
        default_strategies = ['artist title', '"artist" "title"', 'title artist']
        return self._get_nested('npp.search.fallback_strategies', default_strategies)
    
    @property
    def npp_search_exclude_terms(self) -> list:
        """Get terms to exclude from search results."""
        return self._get_nested('npp.search.exclude_terms', [])
    
    @property
    def npp_search_require_terms(self) -> list:
        """Get terms that must be present in search results."""
        return self._get_nested('npp.search.require_terms', [])
    
    # Playlist settings
    @property
    def playlists_fetch_weekly(self) -> bool:
        """Check if weekly playlist fetching is enabled."""
        return self._get_nested('playlists.fetch_weekly', True)
    
    @property
    def playlists_max_tracks(self) -> int:
        """Get maximum tracks per playlist."""
        return self._get_nested('playlists.max_tracks_per_playlist', 50)
    
    @property
    def playlists_tag_prefix(self) -> str:
        """Get tag prefix for downloaded tracks."""
        return self._get_nested('playlists.tag_prefix', 'recotine')
    
    @property
    def raw_config(self) -> Dict[str, Any]:
        """Get raw configuration dictionary."""
        return self._config


def load_config(config_path: Optional[str] = None) -> RecotineConfig:
    """Load Recotine configuration.
    
    Args:
        config_path: Optional path to configuration file
        
    Returns:
        RecotineConfig instance
    """
    return RecotineConfig(config_path)


def regenerate_template(output_path: Optional[str] = None) -> Path:
    """Regenerate the configuration template file from RecotineConfig defaults.
    
    This function programmatically generates a new configuration template
    based on the default values defined in the RecotineConfig class properties.
    This is useful when new configuration options are added or defaults change.
    
    Args:
        output_path: Optional custom output path. Defaults to config/templates/_template_recotine.yaml
        
    Returns:
        Path to the generated template file
        
    Example:
        # Regenerate template to default location
        template_path = regenerate_template()
        
        # Regenerate to custom location
        template_path = regenerate_template("my_custom_template.yaml")
    """
    try:
        # Import here to avoid circular imports
        from .template_generator import regenerate_template as _regenerate_template
        return _regenerate_template(output_path)
    except ImportError:
        try:
            # Try absolute import if relative import fails
            import sys
            from pathlib import Path
            sys.path.insert(0, str(PROJECT_ROOT / "recotine"))
            from template_generator import regenerate_template as _regenerate_template
            return _regenerate_template(output_path)
        except ImportError:
            # Fallback if template_generator is not available
            raise ImportError("Template generator module not found. Please ensure template_generator.py is in the src directory.")