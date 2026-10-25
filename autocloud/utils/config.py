"""Configuration management for AutoCloud."""

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any

from dotenv import load_dotenv
from pydantic import BaseModel, Field


class AutoCloudConfig(BaseModel):
    """AutoCloud configuration model."""

    cloud: str = "azure"
    default_region: str = "eastus"
    anthropic_api_key: str = ""
    terraform_version: str = "1.6.0"
    auto_approve: bool = False
    azure_subscription_id: Optional[str] = None
    debug: bool = False


class ConfigManager:
    """Manages AutoCloud configuration."""

    def __init__(self):
        """Initialize configuration manager."""
        # Load environment variables
        load_dotenv()

        # Set AutoCloud home directory
        self.home_dir = Path(os.getenv("AUTOCLOUD_HOME", Path.home() / ".autocloud"))
        self.config_file = self.home_dir / "config.json"
        self.projects_dir = self.home_dir / "projects"

        # Ensure directories exist
        self.home_dir.mkdir(parents=True, exist_ok=True)
        self.projects_dir.mkdir(parents=True, exist_ok=True)

        # Load or create configuration
        self.config = self._load_config()

    def _load_config(self) -> AutoCloudConfig:
        """Load configuration from file or create default."""
        if self.config_file.exists():
            with open(self.config_file, "r") as f:
                config_data = json.load(f)
                return AutoCloudConfig(**config_data)
        else:
            # Create default configuration
            config = AutoCloudConfig()

            # Override with environment variables if available
            if api_key := os.getenv("ANTHROPIC_API_KEY"):
                config.anthropic_api_key = api_key

            if subscription_id := os.getenv("AZURE_SUBSCRIPTION_ID"):
                config.azure_subscription_id = subscription_id

            if region := os.getenv("AZURE_DEFAULT_REGION"):
                config.default_region = region

            if debug := os.getenv("AUTOCLOUD_DEBUG"):
                config.debug = debug.lower() in ("true", "1", "yes")

            return config

    def save_config(self) -> None:
        """Save configuration to file."""
        with open(self.config_file, "w") as f:
            json.dump(self.config.model_dump(), f, indent=2)

    def set_value(self, key: str, value: Any) -> None:
        """Set a configuration value."""
        if hasattr(self.config, key):
            setattr(self.config, key, value)
            self.save_config()
        else:
            raise ValueError(f"Invalid configuration key: {key}")

    def get_value(self, key: str) -> Any:
        """Get a configuration value."""
        if hasattr(self.config, key):
            return getattr(self.config, key)
        else:
            raise ValueError(f"Invalid configuration key: {key}")

    def get_api_key(self) -> str:
        """Get Anthropic API key from config or environment."""
        # Check environment variable first
        if api_key := os.getenv("ANTHROPIC_API_KEY"):
            return api_key

        # Then check config file
        if self.config.anthropic_api_key:
            return self.config.anthropic_api_key

        raise ValueError(
            "Anthropic API key not found. Please set ANTHROPIC_API_KEY "
            "environment variable or run: autocloud config set anthropic_api_key <key>"
        )

    def is_first_run(self) -> bool:
        """Check if this is the first run of AutoCloud."""
        return not self.config_file.exists()

    def setup_first_run(self, api_key: Optional[str] = None) -> None:
        """Setup configuration on first run."""
        if api_key:
            self.config.anthropic_api_key = api_key

        self.save_config()


# Global configuration instance
_config_manager: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """Get or create global configuration manager."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager
