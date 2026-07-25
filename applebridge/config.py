"""
Configuration Management
========================

Handles configuration loading from config.yaml, logging setup,
and API key loading from multiple sources.
"""

import logging
import os
import yaml
from pathlib import Path


# Default configuration (can be overridden by config.yaml)
CONFIG = {
    "server": {"host": "0.0.0.0", "port": 8080},
    "claude": {"model": "claude-sonnet-4-20250514", "max_tokens": 4096, "timeout": 120},
    "jobs": {"timeout": 180, "max_history": 10, "refresh_interval": 3},
    "files": {"shared_folder": None},
    "history": {"max_entries": 20},
    "proxy": {"block_private_networks": True},
    "setup": {"enabled": True, "require_loopback": True},
    "logging": {"level": "INFO", "file": "claude_bridge.log", "console": True}
}


def load_config(config_file="config.yaml"):
    """Load configuration from YAML file if it exists."""
    global CONFIG
    config_path = Path(__file__).parent.parent / config_file
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = yaml.safe_load(f)
                if user_config:
                    # Deep merge user config into default config
                    for section, values in user_config.items():
                        if section in CONFIG and isinstance(values, dict):
                            CONFIG[section].update(values)
                        else:
                            CONFIG[section] = values
                    logging.info(f"Configuration loaded from {config_path}")
        except Exception as e:
            logging.warning(f"Could not load config file: {e}")
    else:
        logging.info("No config.yaml found, using defaults")


def setup_logging():
    """Setup logging based on configuration."""
    log_level = getattr(logging, CONFIG["logging"]["level"], logging.INFO)
    log_format = '%(asctime)s [%(levelname)s] %(message)s'
    log_date_format = '%Y-%m-%d %H:%M:%S'

    handlers = []

    # Console handler
    if CONFIG["logging"]["console"]:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(log_format, log_date_format))
        handlers.append(console_handler)

    # File handler
    if CONFIG["logging"]["file"]:
        try:
            file_handler = logging.FileHandler(CONFIG["logging"]["file"], encoding='utf-8')
            file_handler.setFormatter(logging.Formatter(log_format, log_date_format))
            handlers.append(file_handler)
        except Exception as e:
            print(f"Warning: Could not setup file logging: {e}")

    logging.basicConfig(
        level=log_level,
        handlers=handlers,
        force=True
    )


def load_api_key():
    """Load API key from multiple locations (in priority order):
    1. Environment variable (already set via export)
    2. ~/.config/anthropic/api_key
    3. .env file in script directory
    """
    # 1. Already in environment?
    if os.environ.get("ANTHROPIC_API_KEY"):
        logging.info("API Key: loaded from environment variable")
        return

    # 2. ~/.config/anthropic/api_key
    config_file = Path.home() / ".config" / "anthropic" / "api_key"
    if config_file.exists():
        key = config_file.read_text().strip()
        if key:
            os.environ["ANTHROPIC_API_KEY"] = key
            logging.info(f"API Key: loaded from {config_file}")
            return

    # 3. .env file next to script
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip("'").strip('"')
                os.environ[key] = value
        if os.environ.get("ANTHROPIC_API_KEY"):
            logging.info(f"API Key: loaded from {env_file}")
            return
