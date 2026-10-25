"""Tests for helper utilities."""

import pytest
from autocloud.utils.helpers import (
    generate_project_id,
    format_cost,
    parse_terraform_resources,
    sanitize_user_input,
)


def test_generate_project_id():
    """Test project ID generation."""
    project_id = generate_project_id()

    assert project_id.startswith("proj-")
    assert len(project_id) == 22  # proj-YYYYMMDD-xxxxxxxx


def test_generate_project_id_unique():
    """Test that project IDs are unique."""
    id1 = generate_project_id()
    id2 = generate_project_id()

    assert id1 != id2


def test_format_cost_usd():
    """Test cost formatting with USD."""
    assert format_cost(100.00, "USD") == "$100.00"
    assert format_cost(50.5, "USD") == "$50.50"
    assert format_cost(0, "USD") == "$0.00"


def test_format_cost_other_currencies():
    """Test cost formatting with other currencies."""
    assert format_cost(100.00, "EUR") == "€100.00"
    assert format_cost(100.00, "GBP") == "£100.00"


def test_parse_terraform_resources():
    """Test parsing Terraform plan output."""
    plan_output = """
    # azurerm_resource_group.example will be created
    + resource "azurerm_resource_group" "example" {
        + id       = (known after apply)
        + location = "eastus"
        + name     = "example-rg"
    }

    # azurerm_virtual_network.main will be created
    + resource "azurerm_virtual_network" "main" {
        + id   = (known after apply)
        + name = "example-vnet"
    }
    """

    resources = parse_terraform_resources(plan_output)

    assert len(resources) == 2
    assert "azurerm_resource_group.example" in resources
    assert "azurerm_virtual_network.main" in resources


def test_sanitize_user_input():
    """Test input sanitization."""
    # Test dangerous characters removed
    assert sanitize_user_input("test; rm -rf /") == "test rm -rf /"
    assert sanitize_user_input("test && malicious") == "test  malicious"
    assert sanitize_user_input("test | grep") == "test  grep"

    # Test safe input unchanged
    assert sanitize_user_input("create 2 VMs") == "create 2 VMs"
