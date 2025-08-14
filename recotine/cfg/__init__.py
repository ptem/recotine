"""Configuration management for Recotine.

This module provides configuration loading and template generation functionality.
"""

from recotine.cfg.config import load_config, RecotineConfig, regenerate_template
from recotine.cfg.template_generator import regenerate_template as template_regenerate_template

__all__ = [
    "load_config",
    "RecotineConfig",
    "regenerate_template",
    "template_regenerate_template",
]