"""Helper utilities for AutoCloud."""

import json
import secrets
import string
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple


def generate_project_id() -> str:
    """Generate a unique project ID in format: proj-YYYYMMDD-{random-8-chars}."""
    date_str = datetime.now().strftime("%Y%m%d")
    random_str = "".join(
        secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8)
    )
    return f"proj-{date_str}-{random_str}"


def save_project_metadata(project_dir: Path, metadata: Dict[str, Any]) -> None:
    """Save project metadata to JSON file."""
    metadata_file = project_dir / "metadata.json"
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)


def load_project_metadata(project_dir: Path) -> Optional[Dict[str, Any]]:
    """Load project metadata from JSON file."""
    metadata_file = project_dir / "metadata.json"
    if not metadata_file.exists():
        return None

    with open(metadata_file, "r") as f:
        return json.load(f)


def get_all_projects(projects_dir: Path) -> list[Dict[str, Any]]:
    """Get metadata for all projects."""
    projects = []

    if not projects_dir.exists():
        return projects

    for project_dir in projects_dir.iterdir():
        if project_dir.is_dir() and project_dir.name.startswith("proj-"):
            metadata = load_project_metadata(project_dir)
            if metadata:
                metadata["path"] = str(project_dir)
                projects.append(metadata)

    # Sort by creation date (newest first)
    projects.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    return projects


def find_project_by_id(projects_dir: Path, project_id: str) -> Optional[Path]:
    """Find project directory by ID."""
    project_dir = projects_dir / project_id

    if project_dir.exists() and project_dir.is_dir():
        return project_dir

    return None


def format_cost(amount: float, currency: str = "USD") -> str:
    """Format cost amount with currency symbol."""
    symbols = {"USD": "$", "EUR": "€", "GBP": "£"}
    symbol = symbols.get(currency, currency)
    return f"{symbol}{amount:.2f}"


def parse_terraform_resources(plan_output: str) -> list[str]:
    """Parse Terraform plan output to extract resource names."""
    resources = []

    for line in plan_output.split("\n"):
        line = line.strip()
        # Look for lines like "# azurerm_virtual_machine.example will be created"
        if "will be created" in line or "will be updated" in line:
            if line.startswith("#"):
                parts = line.split()
                if len(parts) >= 2:
                    resources.append(parts[1])

    return resources


def sanitize_user_input(input_str: str) -> str:
    """Sanitize user input to prevent command injection."""
    # Remove dangerous characters
    dangerous_chars = [";", "&", "|", "`", "$", "(", ")", "<", ">", "\n", "\r"]

    sanitized = input_str
    for char in dangerous_chars:
        sanitized = sanitized.replace(char, "")

    return sanitized.strip()


def check_terraform_installed() -> bool:
    """Check if Terraform is installed."""
    import shutil

    return shutil.which("terraform") is not None


def check_azure_cli_installed() -> bool:
    """Check if Azure CLI is installed."""
    import shutil

    return shutil.which("az") is not None


def get_azure_account_info() -> Optional[Dict[str, Any]]:
    """Get Azure account information from Azure CLI."""
    import subprocess
    import json

    try:
        result = subprocess.run(
            ["az", "account", "show"],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError):
        return None


def find_ssh_public_key(custom_path: Optional[str] = None) -> Tuple[Optional[str], Optional[Path]]:
    """
    Find SSH public key for Linux VM authentication.

    Priority:
    1. Custom path provided by user
    2. ~/.ssh/id_ed25519.pub (modern, recommended)
    3. ~/.ssh/id_rsa.pub (traditional, widely compatible)

    Args:
        custom_path: Optional custom path to SSH public key

    Returns:
        Tuple of (ssh_key_content, ssh_key_path) or (None, None) if not found
    """
    home = Path.home()

    # Check custom path first
    if custom_path:
        custom_key_path = Path(custom_path).expanduser()
        if custom_key_path.exists() and custom_key_path.is_file():
            try:
                key_content = custom_key_path.read_text().strip()
                if validate_ssh_public_key(key_content):
                    return key_content, custom_key_path
            except Exception:
                pass
        return None, None

    # Check standard SSH key locations
    standard_paths = [
        home / ".ssh" / "id_ed25519.pub",  # Modern Ed25519 key (preferred)
        home / ".ssh" / "id_rsa.pub",      # Traditional RSA key
    ]

    for key_path in standard_paths:
        if key_path.exists() and key_path.is_file():
            try:
                key_content = key_path.read_text().strip()
                if validate_ssh_public_key(key_content):
                    return key_content, key_path
            except Exception:
                continue

    return None, None


def validate_ssh_public_key(key_content: str) -> bool:
    """
    Validate SSH public key format.

    Args:
        key_content: SSH public key content

    Returns:
        True if valid, False otherwise
    """
    if not key_content or not isinstance(key_content, str):
        return False

    key_content = key_content.strip()

    # SSH public keys typically start with these prefixes
    valid_prefixes = [
        "ssh-rsa ",
        "ssh-ed25519 ",
        "ecdsa-sha2-nistp256 ",
        "ecdsa-sha2-nistp384 ",
        "ecdsa-sha2-nistp521 ",
    ]

    return any(key_content.startswith(prefix) for prefix in valid_prefixes)


def get_ssh_key_instructions() -> str:
    """
    Get instructions for generating SSH keys.

    Returns:
        Formatted instructions string
    """
    return """
SSH Key Not Found

AutoCloud requires an SSH public key for secure Linux VM authentication.

Quick Setup:

  1. Generate a new SSH key pair:
     ssh-keygen -t ed25519 -C "your_email@example.com"

  2. Press Enter to accept default location (~/.ssh/id_ed25519)
  3. Set a passphrase (or press Enter for no passphrase)
  4. Re-run AutoCloud - your key will be detected automatically

Alternative: Specify a custom SSH key:
  autocloud deploy "request" --ssh-key-path /path/to/key.pub

Standard key locations checked:
  • ~/.ssh/id_ed25519.pub (preferred, modern)
  • ~/.ssh/id_rsa.pub (traditional, widely compatible)

For more info: https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent
"""
