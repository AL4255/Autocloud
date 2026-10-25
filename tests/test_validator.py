"""Tests for Terraform validator."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from autocloud.core.validator import TerraformValidator


@pytest.fixture
def temp_project_dir(tmp_path):
    """Create a temporary project directory."""
    project_dir = tmp_path / "test-project"
    project_dir.mkdir()
    return project_dir


@pytest.fixture
def mock_subprocess():
    """Mock subprocess.run."""
    with patch("autocloud.core.validator.subprocess.run") as mock:
        yield mock


def test_validator_initialization(temp_project_dir):
    """Test validator initializes correctly."""
    validator = TerraformValidator(temp_project_dir)

    assert validator.project_dir == temp_project_dir
    assert validator.MAX_RETRIES == 3


def test_terraform_init_success(temp_project_dir, mock_subprocess):
    """Test successful terraform init."""
    mock_subprocess.return_value = MagicMock(
        returncode=0,
        stdout="Terraform initialized",
        stderr=""
    )

    validator = TerraformValidator(temp_project_dir)
    success, output = validator.terraform_init()

    assert success is True
    assert "Terraform initialized" in output
    mock_subprocess.assert_called_once()


def test_terraform_init_failure(temp_project_dir, mock_subprocess):
    """Test failed terraform init."""
    mock_subprocess.return_value = MagicMock(
        returncode=1,
        stdout="",
        stderr="Error: initialization failed"
    )

    validator = TerraformValidator(temp_project_dir)
    success, output = validator.terraform_init()

    assert success is False
    assert "initialization failed" in output


def test_terraform_validate_success(temp_project_dir, mock_subprocess):
    """Test successful terraform validate."""
    mock_subprocess.return_value = MagicMock(
        returncode=0,
        stdout="Success! The configuration is valid.",
        stderr=""
    )

    validator = TerraformValidator(temp_project_dir)
    success, output = validator.terraform_validate()

    assert success is True
    assert "valid" in output


def test_terraform_validate_failure(temp_project_dir, mock_subprocess):
    """Test failed terraform validate."""
    mock_subprocess.return_value = MagicMock(
        returncode=1,
        stdout="",
        stderr="Error: Invalid resource configuration"
    )

    validator = TerraformValidator(temp_project_dir)
    success, output = validator.terraform_validate()

    assert success is False
    assert "Invalid resource" in output
