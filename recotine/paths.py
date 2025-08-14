"""Centralized path definitions for accessing project root directories.

This module provides constants for accessing directories at the project root
level, such as config/, recs/, etc. All modules that need to access these
directories should use these centralized constants.
"""

from pathlib import Path

# Get the project root directory (parent of the recotine package)
PROJECT_ROOT = Path(__file__).parent.parent

# Define standardized directory paths
CONFIG_DIR = PROJECT_ROOT / "config"
OUTPUT_DIR = PROJECT_ROOT / "recs"

# Additional directories that might be needed
TEMPLATES_DIR = CONFIG_DIR / "templates"