"""Template generator for Recotine configuration files.

This module provides functionality to programmatically regenerate the configuration
template based on the defaults defined in the RecotineConfig class.
"""

from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from recotine.cfg.config import RecotineConfig
from recotine.paths import TEMPLATES_DIR


class TemplateGenerator:
    """Generates configuration templates from RecotineConfig defaults."""
    
    def __init__(self):
        """Initialize the template generator."""
        # Don't load config file, just use the class for extracting defaults
        self.config_class = RecotineConfig
        self.template_structure = {}
        
    def extract_defaults(self) -> Dict[str, Any]:
        """Extract default values from existing template file.
        
        Returns:
            Dictionary with nested configuration structure and defaults from template
        """
        defaults = {}
        
        # Try to load existing template file to get current defaults
        template_path = TEMPLATES_DIR / "_template_recotine.yaml"
        if template_path.exists():
            try:
                with open(template_path, 'r', encoding='utf-8') as f:
                    template_data = yaml.safe_load(f)
                    
                # Extract the configuration values from the template
                # Skip user credential placeholders and use actual config values
                if template_data:
                    # Extract NPP configuration
                    if 'npp' in template_data:
                        defaults['npp'] = template_data['npp'].copy()
                    
                    # Extract playlist configuration  
                    if 'playlists' in template_data:
                        defaults['playlists'] = template_data['playlists'].copy()
                        
                    print(f"✅ Loaded defaults from existing template: {template_path}")
                    return defaults
                    
            except Exception as e:
                print(f"Warning: Could not load existing template {template_path}: {e}")
        
        # Fallback to hardcoded defaults if template doesn't exist or can't be loaded
        print("⚠️ Using fallback defaults since template couldn't be loaded")
        defaults = {
            'npp': {
                'network_mode': 'host',
                'use_music_library': True,
                'search': {
                    'allowed_extensions': ['mp3', 'flac', 'ogg', 'm4a', 'wma'],
                    'min_bitrate': 320,
                    'max_bitrate': None,
                    'prefer_lossless': True,
                    'require_free_slots': True,
                    'max_wait_time': 15,
                    'max_file_size_mb': 50,
                    'min_similarity': 0.5,
                    'max_search_attempts': 4,
                    'fallback_strategies': [
                        'artist title',
                        '"artist" with title includes',
                        '"artist" "title"',
                        'title artist'
                    ],
                    'sufficient_similarity': 0.8,
                    'exclude_terms': [],
                    'require_terms': []
                }
            },
            'playlists': {
                'fetch_weekly': True,
                'max_tracks_per_playlist': 50,
                'tag_prefix': 'recotine'
            }
        }

        return defaults
    
    def _set_nested_value(self, data: Dict, key_path: str, value: Any):
        """Set a nested dictionary value using dot notation.
        
        Args:
            data: Dictionary to modify
            key_path: Dot-separated path (e.g., 'npp.search.min_bitrate')
            value: Value to set
        """
        keys = key_path.split('.')
        current = data
        
        # Navigate to the parent of the target key
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        # Set the final value
        current[keys[-1]] = value
    
    def generate_template_content(self) -> str:
        """Generate the complete template content as a YAML string.
        
        Returns:
            YAML template content with comments
        """
        defaults = self.extract_defaults()
        
        # Template header
        template_lines = [
            "# Recotine Configuration Template",
            "# Copy this file to config/recotine.yaml and fill in your credentials",
            "",
        ]
        
        # Last.fm section
        template_lines.extend([
            "# Last.fm API Configuration",
            "lastfm:",
            '  username: "your_lastfm_username"',
            '  api_key: "your_lastfm_api_key"',
            '  api_secret: "your_lastfm_api_secret"',
            '  session_key: ""  # Will be populated automatically after authentication',
            "",
        ])
        
        # ListenBrainz section
        template_lines.extend([
            "# ListenBrainz Configuration",
            "listenbrainz:",
            '  username: "your_listenbrainz_username"',
            '  user_token: "your_listenbrainz_user_token"',
            "",
        ])
        
        # Music section
        template_lines.extend([
            "# Music Library Configuration",
            "music:",
            '  library_path: "/path/to/your/music/library"  # Path to your music SHARE library for nicotine++. Please share to others if downloading.',
            "  output_path: \"/path/to/downloads\"            # Where finished playlist tracks (that aren't in your library already) are placed",
            "",
        ])
        
        # Navidrome section (optional)
        template_lines.extend([
            "# Navidrome/Subsonic Configuration (Optional)",
            "navidrome:",
            '  url: "http://your-navidrome-server:4533"',
            '  username: "your_navidrome_username"',
            '  password: "your_navidrome_password"',
            "",
        ])
        
        # NPP section with dynamic defaults
        npp_defaults = defaults.get('npp', {})
        search_defaults = npp_defaults.get('search', {})
        
        template_lines.extend([
            "# Nicotine++ Docker Configuration (Optional)",
            "npp:",
            f"  network_mode: {npp_defaults.get('network_mode', 'host')}    # Passthrough network to home system (Useful if using a VPN on your docker host)",
            f"  use_music_library: {str(npp_defaults.get('use_music_library', True)).lower()} # Use music/library_path as the shared files dir for nicotine++.",
            "  ",
            "  # Search restrictions and preferences",
            "  search:",
            "    # File format preferences (in order of preference)",
            f"    allowed_extensions: {search_defaults.get('allowed_extensions', ['mp3', 'flac', 'ogg', 'm4a'])}",
            "    ",
            "    # Audio quality requirements",
            f"    min_bitrate: {search_defaults.get('min_bitrate', 320)}          # Minimum acceptable bitrate (kbps)",
            f"    max_bitrate: {search_defaults.get('max_bitrate', 'null')}         # Maximum bitrate (null = no limit)",
            f"    prefer_lossless: {str(search_defaults.get('prefer_lossless', True)).lower()}    # Prefer lossless formats when available",
            "    ",
            "    # Search behavior",
            f"    require_free_slots: {str(search_defaults.get('require_free_slots', True)).lower()}  # Only download from users with free slots",
            f"    max_wait_time: {search_defaults.get('max_wait_time', 15)}         # Maximum time to wait for search results (seconds)",
            f"    max_file_size_mb: {search_defaults.get('max_file_size_mb', 50)}     # Maximum file size in MB (null = no limit)",
            f"    min_similarity: {search_defaults.get('min_similarity', 0.5)}       # Minimum similarity score to search query (0.0-1.0)",
            "    ",
            "    # Search attempt strategies",
            f"    max_search_attempts: {search_defaults.get('max_search_attempts', 3)}    # Maximum number of different search queries to try",
            "    fallback_strategies:      # Different query formats to try in order",
        ])
        
        # Add fallback strategies with proper indentation
        fallback_strategies = search_defaults.get('fallback_strategies', [
            'artist title', '"artist" "title"', 'title artist', '"artist" with title includes'
        ])
        
        # Ensure fallback_strategies is a list
        if isinstance(fallback_strategies, str):
            # If it's a string, it might be a single strategy or malformed
            fallback_strategies = [fallback_strategies]
        elif not isinstance(fallback_strategies, list):
            # Use complete default set if not a proper list
            fallback_strategies = ['artist title', '"artist" "title"', 'title artist', '"artist" with title includes']
        
        strategy_comments = {
            'artist title': '# Standard format',
            '"artist" "title"': '# Quoted format',
            'title artist': '# Reversed format',
            '"artist" with title includes': '# Quoted artist with title in includes_text'
        }
        
        for strategy in fallback_strategies:
            comment = strategy_comments.get(strategy, '')
            # Format each strategy according to the exact specification
            if strategy == '"artist" "title"':
                # Escape the internal quotes: "\"artist\" \"title\""
                template_lines.append(f'      - "\\"artist\\" \\"title\\""   {comment}')
            elif strategy == '"artist" with title includes':
                # Escape the internal quotes: "\"artist\" with title includes"
                template_lines.append(f'      - "\\"artist\\" with title includes"  {comment}')
            else:
                # For strategies without internal quotes, use standard double quotes
                template_lines.append(f'      - "{strategy}"           {comment}')
        
        template_lines.extend([
            "    ",
            "    # Search quality thresholds",
            f"    sufficient_similarity: {search_defaults.get('sufficient_similarity', 0.8)}  # Stop trying fallback strategies if this similarity is reached (0.0-1.0)",
            "    ",
            "    # Content filtering",
            f"    exclude_terms: {search_defaults.get('exclude_terms', [])}         # Terms to avoid (empty = none excluded by default)",
            f"    require_terms: {search_defaults.get('require_terms', [])}         # Terms that must be present (empty = none required)",
            "",
        ])
        
        # Playlist section
        playlists_defaults = defaults.get('playlists', {})
        template_lines.extend([
            "# Playlist Settings",
            "playlists:",
            f"  fetch_weekly: {str(playlists_defaults.get('fetch_weekly', True)).lower()}",
            f"  max_tracks_per_playlist: {playlists_defaults.get('max_tracks_per_playlist', 50)}",
            f'  tag_prefix: "{playlists_defaults.get("tag_prefix", "recotine")}"',
        ])
        
        return "\n".join(template_lines)
    
    def regenerate_template(self, output_path: Optional[str] = None) -> Path:
        """Regenerate the configuration template file.
        
        Args:
            output_path: Optional custom output path. Defaults to config/templates/_template_recotine.yaml
            
        Returns:
            Path to the generated template file
        """
        if output_path is None:
            output_path = TEMPLATES_DIR / "_template_recotine.yaml"
        else:
            output_path = Path(output_path)
        
        # Ensure the directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Generate template content
        template_content = self.generate_template_content()
        
        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(template_content)
        
        print(f"✅ Template regenerated successfully: {output_path}")
        return output_path


def regenerate_template(output_path: Optional[str] = None) -> Path:
    """Convenience function to regenerate the configuration template.
    
    Args:
        output_path: Optional custom output path
        
    Returns:
        Path to the generated template file
    """
    generator = TemplateGenerator()
    return generator.regenerate_template(output_path)


if __name__ == "__main__":
    # Command line usage
    import sys
    
    output_path = sys.argv[1] if len(sys.argv) > 1 else None
    regenerated_path = regenerate_template(output_path)
    print(f"Template regenerated at: {regenerated_path}")