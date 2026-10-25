"""Tests for Terraform generator."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from autocloud.core.generator import TerraformGenerator


@pytest.fixture
def temp_project_dir(tmp_path):
    """Create a temporary project directory."""
    return tmp_path / "test-project"


@pytest.fixture
def mock_claude_client():
    """Mock Claude client."""
    with patch("autocloud.core.generator.ClaudeClient") as mock:
        yield mock


def test_generator_initialization(temp_project_dir):
    """Test generator initializes correctly."""
    generator = TerraformGenerator(temp_project_dir, "test-api-key")

    assert generator.project_dir == temp_project_dir
    assert temp_project_dir.exists()


def test_write_files(temp_project_dir):
    """Test writing Terraform files."""
    generator = TerraformGenerator(temp_project_dir, "test-api-key")

    files = {
        "main.tf": "resource \"azurerm_resource_group\" \"example\" {}",
        "variables.tf": "variable \"location\" {}",
        "outputs.tf": "output \"rg_name\" {}",
    }

    generator.write_files(files)

    # Verify files were created
    for filename, content in files.items():
        file_path = temp_project_dir / filename
        assert file_path.exists()
        assert file_path.read_text() == content


def test_read_current_files(temp_project_dir):
    """Test reading Terraform files."""
    generator = TerraformGenerator(temp_project_dir, "test-api-key")

    # Write some files
    files = {
        "main.tf": "resource content",
        "variables.tf": "variable content",
    }
    generator.write_files(files)

    # Read them back
    read_files = generator.read_current_files()

    assert read_files == files
