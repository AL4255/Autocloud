"""
Unit tests for Azure Connection Fixer.

Tests the complete pipeline:
1. Parsing Terraform HCL
2. Detecting missing connections
3. Generating Terraform code
4. Injecting fixes into main.tf
"""

import pytest
from autocloud.core.connection_fixer import AzureConnectionFixer, MissingConnection
from autocloud.core.connection_rules import (
    AZURE_CONNECTION_RULES,
    NSG_TO_NIC_RULE,
    LOAD_BALANCER_TO_VMS_RULE,
    ROUTE_TABLE_TO_SUBNET_RULE
)


# ==============================================================================
# TEST 1: TERRAFORM PARSING
# ==============================================================================

class TestTerraformParsing:
    """Test the HCL parsing functionality."""

    def test_parse_empty_terraform(self):
        """Empty content should return empty dict."""
        fixer = AzureConnectionFixer({})
        result = fixer.parse_terraform_resources("")

        assert result == {}

    def test_parse_single_resource(self):
        """Parse a single resource."""
        terraform = '''
resource "azurerm_resource_group" "main" {
  name     = "test-rg"
  location = "eastus"
}
'''
        fixer = AzureConnectionFixer({})
        result = fixer.parse_terraform_resources(terraform)

        assert "azurerm_resource_group" in result
        assert result["azurerm_resource_group"] == ["main"]

    def test_parse_multiple_resources_same_type(self):
        """Parse multiple resources of the same type."""
        terraform = '''
resource "azurerm_network_interface" "vm1_nic" {
  name = "vm1-nic"
}

resource "azurerm_network_interface" "vm2_nic" {
  name = "vm2-nic"
}

resource "azurerm_network_interface" "vm3_nic" {
  name = "vm3-nic"
}
'''
        fixer = AzureConnectionFixer({})
        result = fixer.parse_terraform_resources(terraform)

        assert "azurerm_network_interface" in result
        assert len(result["azurerm_network_interface"]) == 3
        assert "vm1_nic" in result["azurerm_network_interface"]
        assert "vm2_nic" in result["azurerm_network_interface"]
        assert "vm3_nic" in result["azurerm_network_interface"]

    def test_parse_multiple_resource_types(self):
        """Parse mixed resource types."""
        terraform = '''
resource "azurerm_resource_group" "main" {
  name = "test-rg"
}

resource "azurerm_virtual_network" "main" {
  name = "test-vnet"
}

resource "azurerm_subnet" "app" {
  name = "app-subnet"
}

resource "azurerm_subnet" "db" {
  name = "db-subnet"
}
'''
        fixer = AzureConnectionFixer({})
        result = fixer.parse_terraform_resources(terraform)

        assert len(result) == 3
        assert "azurerm_resource_group" in result
        assert "azurerm_virtual_network" in result
        assert "azurerm_subnet" in result
        assert len(result["azurerm_subnet"]) == 2


# ==============================================================================
# TEST 2: NSG CONNECTION DETECTION (SIMPLE CASE)
# ==============================================================================

class TestNSGConnectionDetection:
    """Test detection of missing NSG-to-NIC associations."""

    def test_nsg_with_no_nics(self):
        """NSG exists but no NICs - no missing connections."""
        terraform = '''
resource "azurerm_network_security_group" "web_nsg" {
  name = "web-nsg"
}
'''
        fixer = AzureConnectionFixer({"nsg_to_nic": NSG_TO_NIC_RULE})
        resources = fixer.parse_terraform_resources(terraform)
        missing = fixer.detect_missing_connections(resources)

        assert len(missing) == 0

    def test_nic_with_no_nsg(self):
        """NIC exists but no NSG - no missing connections."""
        terraform = '''
resource "azurerm_network_interface" "vm1_nic" {
  name = "vm1-nic"
}
'''
        fixer = AzureConnectionFixer({"nsg_to_nic": NSG_TO_NIC_RULE})
        resources = fixer.parse_terraform_resources(terraform)
        missing = fixer.detect_missing_connections(resources)

        assert len(missing) == 0

    def test_nsg_and_nic_without_association(self):
        """NSG + NIC exist but association missing - should detect."""
        terraform = '''
resource "azurerm_network_security_group" "web_nsg" {
  name = "web-nsg"
}

resource "azurerm_network_interface" "vm1_nic" {
  name = "vm1-nic"
}
'''
        fixer = AzureConnectionFixer({"nsg_to_nic": NSG_TO_NIC_RULE})
        resources = fixer.parse_terraform_resources(terraform)
        missing = fixer.detect_missing_connections(resources)

        assert len(missing) == 1
        assert missing[0].rule_name == "nsg_to_nic"
        assert missing[0].primary_resource == ("azurerm_network_security_group", "web_nsg")
        assert ("azurerm_network_interface", "vm1_nic") in missing[0].target_resources

    def test_nsg_and_nic_with_association(self):
        """NSG + NIC + association exist - no missing connections."""
        terraform = '''
resource "azurerm_network_security_group" "web_nsg" {
  name = "web-nsg"
}

resource "azurerm_network_interface" "vm1_nic" {
  name = "vm1-nic"
}

resource "azurerm_network_interface_security_group_association" "vm1_nsg_assoc" {
  network_interface_id      = azurerm_network_interface.vm1_nic.id
  network_security_group_id = azurerm_network_security_group.web_nsg.id
}
'''
        fixer = AzureConnectionFixer({"nsg_to_nic": NSG_TO_NIC_RULE})
        resources = fixer.parse_terraform_resources(terraform)
        missing = fixer.detect_missing_connections(resources)

        assert len(missing) == 0


# ==============================================================================
# TEST 3: LOAD BALANCER CONNECTION DETECTION (COMPLEX CASE)
# ==============================================================================

class TestLoadBalancerConnectionDetection:
    """Test detection of missing Load Balancer associations."""

    def test_lb_without_nics(self):
        """LB exists but no NICs - no missing connections."""
        terraform = '''
resource "azurerm_lb" "web_lb" {
  name = "web-lb"
}
'''
        fixer = AzureConnectionFixer({"load_balancer_to_vms": LOAD_BALANCER_TO_VMS_RULE})
        resources = fixer.parse_terraform_resources(terraform)
        missing = fixer.detect_missing_connections(resources)

        assert len(missing) == 0

    def test_lb_and_nics_no_associations(self):
        """LB + NICs exist but all 4 associations missing."""
        terraform = '''
resource "azurerm_lb" "web_lb" {
  name = "web-lb"
}

resource "azurerm_network_interface" "vm1_nic" {
  name = "vm1-nic"
}

resource "azurerm_network_interface" "vm2_nic" {
  name = "vm2-nic"
}
'''
        fixer = AzureConnectionFixer({"load_balancer_to_vms": LOAD_BALANCER_TO_VMS_RULE})
        resources = fixer.parse_terraform_resources(terraform)
        missing = fixer.detect_missing_connections(resources)

        # Should detect 4 missing association types
        assert len(missing) == 4

        # Check that all 4 types are detected
        missing_types = {m.association_config["type"] for m in missing}
        assert "azurerm_lb_backend_address_pool" in missing_types
        assert "azurerm_network_interface_backend_address_pool_association" in missing_types
        assert "azurerm_lb_probe" in missing_types
        assert "azurerm_lb_rule" in missing_types

    def test_lb_with_partial_associations(self):
        """LB + NICs with only backend pool - should detect 3 missing."""
        terraform = '''
resource "azurerm_lb" "web_lb" {
  name = "web-lb"
}

resource "azurerm_network_interface" "vm1_nic" {
  name = "vm1-nic"
}

resource "azurerm_lb_backend_address_pool" "web_lb_backend_pool" {
  loadbalancer_id = azurerm_lb.web_lb.id
}
'''
        fixer = AzureConnectionFixer({"load_balancer_to_vms": LOAD_BALANCER_TO_VMS_RULE})
        resources = fixer.parse_terraform_resources(terraform)
        missing = fixer.detect_missing_connections(resources)

        # Backend pool exists, so should detect 3 missing
        assert len(missing) == 3

        missing_types = {m.association_config["type"] for m in missing}
        assert "azurerm_network_interface_backend_address_pool_association" in missing_types
        assert "azurerm_lb_probe" in missing_types
        assert "azurerm_lb_rule" in missing_types


# ==============================================================================
# TEST 4: TERRAFORM GENERATION
# ==============================================================================

class TestTerraformGeneration:
    """Test Terraform code generation from missing connections."""

    def test_generate_single_count_resource(self):
        """Generate a single-count resource (backend pool)."""
        missing = MissingConnection(
            rule_name="load_balancer_to_vms",
            primary_resource=("azurerm_lb", "web_lb"),
            target_resources=[("azurerm_network_interface", "vm1_nic")],
            association_config={
                "type": "azurerm_lb_backend_address_pool",
                "count": "single",
                "template": '''resource "azurerm_lb_backend_address_pool" "{assoc_name}" {{
  loadbalancer_id = azurerm_lb.{primary_name}.id
  name            = "backend-pool"
}}''',
                "name_pattern": "{primary_name}_backend_pool"
            },
            description="Test"
        )

        fixer = AzureConnectionFixer({})
        terraform_blocks = fixer.generate_connection_terraform(missing)

        assert len(terraform_blocks) == 1
        assert "web_lb_backend_pool" in terraform_blocks[0]
        assert "azurerm_lb.web_lb.id" in terraform_blocks[0]
        assert "backend-pool" in terraform_blocks[0]

    def test_generate_per_target_resources(self):
        """Generate per-target resources (one per NIC)."""
        missing = MissingConnection(
            rule_name="load_balancer_to_vms",
            primary_resource=("azurerm_lb", "web_lb"),
            target_resources=[
                ("azurerm_network_interface", "vm1_nic"),
                ("azurerm_network_interface", "vm2_nic"),
                ("azurerm_network_interface", "vm3_nic")
            ],
            association_config={
                "type": "azurerm_network_interface_backend_address_pool_association",
                "count": "per_target",
                "template": '''resource "azurerm_network_interface_backend_address_pool_association" "{assoc_name}" {{
  network_interface_id    = azurerm_network_interface.{target_name}.id
  ip_configuration_name   = "internal"
  backend_address_pool_id = azurerm_lb_backend_address_pool.{primary_name}_backend_pool.id
}}''',
                "name_pattern": "{primary_name}_{target_name}_pool_assoc"
            },
            description="Test"
        )

        fixer = AzureConnectionFixer({})
        terraform_blocks = fixer.generate_connection_terraform(missing)

        # Should generate 3 resources (one per NIC)
        assert len(terraform_blocks) == 3

        # Check each has correct NIC reference
        assert "web_lb_vm1_nic_pool_assoc" in terraform_blocks[0]
        assert "web_lb_vm2_nic_pool_assoc" in terraform_blocks[1]
        assert "web_lb_vm3_nic_pool_assoc" in terraform_blocks[2]

        # Check references
        assert "azurerm_network_interface.vm1_nic.id" in terraform_blocks[0]
        assert "azurerm_network_interface.vm2_nic.id" in terraform_blocks[1]
        assert "azurerm_network_interface.vm3_nic.id" in terraform_blocks[2]


# ==============================================================================
# TEST 5: FULL INTEGRATION (DETECT + GENERATE + INJECT)
# ==============================================================================

class TestFullPipeline:
    """Test the complete fix pipeline."""

    def test_fix_nsg_connections(self):
        """Full pipeline: NSG + NIC without association."""
        original_terraform = '''resource "azurerm_network_security_group" "web_nsg" {
  name                = "web-nsg"
  location            = "eastus"
  resource_group_name = azurerm_resource_group.main.name

  security_rule {
    name                       = "allow-http"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "80"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }
}

resource "azurerm_network_interface" "vm1_nic" {
  name                = "vm1-nic"
  location            = "eastus"
  resource_group_name = azurerm_resource_group.main.name

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.main.id
    private_ip_address_allocation = "Dynamic"
  }
}'''

        fixer = AzureConnectionFixer({"nsg_to_nic": NSG_TO_NIC_RULE})
        fixed_terraform, descriptions = fixer.fix_terraform(original_terraform)

        # Should have one fix
        assert len(descriptions) == 1

        # Fixed version should include association
        assert "azurerm_network_interface_security_group_association" in fixed_terraform
        assert "web_nsg_vm1_nic_nsg_assoc" in fixed_terraform

        # Should include header
        assert "AUTO-GENERATED BY AUTOCLOUD CONNECTION FIXER" in fixed_terraform

        # Original content should still be there
        assert "web-nsg" in fixed_terraform
        assert "vm1-nic" in fixed_terraform

    def test_fix_load_balancer_connections(self):
        """Full pipeline: LB + NICs with all missing associations."""
        original_terraform = '''resource "azurerm_lb" "web_lb" {
  name                = "web-lb"
  location            = "eastus"
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "Standard"

  frontend_ip_configuration {
    name                 = "public-ip"
    public_ip_address_id = azurerm_public_ip.lb_ip.id
  }
}

resource "azurerm_network_interface" "vm1_nic" {
  name                = "vm1-nic"
  location            = "eastus"
  resource_group_name = azurerm_resource_group.main.name

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.main.id
    private_ip_address_allocation = "Dynamic"
  }
}

resource "azurerm_network_interface" "vm2_nic" {
  name                = "vm2-nic"
  location            = "eastus"
  resource_group_name = azurerm_resource_group.main.name

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.main.id
    private_ip_address_allocation = "Dynamic"
  }
}'''

        fixer = AzureConnectionFixer({"load_balancer_to_vms": LOAD_BALANCER_TO_VMS_RULE})
        fixed_terraform, descriptions = fixer.fix_terraform(original_terraform)

        # Should have 4 fixes (backend pool, 2x NIC assoc, health probe, LB rule)
        # Actually 6 total: 1 pool + 2 NIC assocs + 1 probe + 1 rule = 5... wait let me think
        # The rule generates: 1 backend pool, 1 health probe, 1 LB rule, 2 NIC associations
        # But MissingConnection is per association_config, not per resource
        # So it's 4 MissingConnection objects (one for each type in required_connections)
        assert len(descriptions) == 4

        # Check all 4 association types were generated
        assert "azurerm_lb_backend_address_pool" in fixed_terraform
        assert "web_lb_backend_pool" in fixed_terraform

        assert "azurerm_lb_probe" in fixed_terraform
        assert "web_lb_health_probe" in fixed_terraform

        assert "azurerm_lb_rule" in fixed_terraform
        assert "web_lb_lb_rule" in fixed_terraform

        assert "azurerm_network_interface_backend_address_pool_association" in fixed_terraform
        assert "web_lb_vm1_nic_pool_assoc" in fixed_terraform
        assert "web_lb_vm2_nic_pool_assoc" in fixed_terraform

        # Original should still be there
        assert "web-lb" in fixed_terraform
        assert "vm1-nic" in fixed_terraform
        assert "vm2-nic" in fixed_terraform

    def test_no_fixes_needed(self):
        """Pipeline with complete Terraform - no fixes needed."""
        complete_terraform = '''resource "azurerm_network_security_group" "web_nsg" {
  name = "web-nsg"
}

resource "azurerm_network_interface" "vm1_nic" {
  name = "vm1-nic"
}

resource "azurerm_network_interface_security_group_association" "vm1_nsg_assoc" {
  network_interface_id      = azurerm_network_interface.vm1_nic.id
  network_security_group_id = azurerm_network_security_group.web_nsg.id
}'''

        fixer = AzureConnectionFixer({"nsg_to_nic": NSG_TO_NIC_RULE})
        fixed_terraform, descriptions = fixer.fix_terraform(complete_terraform)

        # No fixes needed
        assert len(descriptions) == 0

        # Content should be unchanged
        assert fixed_terraform == complete_terraform


# ==============================================================================
# TEST 6: MULTIPLE RULES
# ==============================================================================

class TestMultipleRules:
    """Test scenarios with multiple connection rules active."""

    def test_multiple_patterns_detected(self):
        """Detect missing connections across multiple rules."""
        terraform = '''
resource "azurerm_network_security_group" "web_nsg" {
  name = "web-nsg"
}

resource "azurerm_route_table" "custom_routes" {
  name = "custom-routes"
}

resource "azurerm_network_interface" "vm1_nic" {
  name = "vm1-nic"
}

resource "azurerm_subnet" "app_subnet" {
  name = "app-subnet"
}
'''
        rules = {
            "nsg_to_nic": NSG_TO_NIC_RULE,
            "route_table_to_subnet": ROUTE_TABLE_TO_SUBNET_RULE
        }

        fixer = AzureConnectionFixer(rules)
        resources = fixer.parse_terraform_resources(terraform)
        missing = fixer.detect_missing_connections(resources)

        # Should detect missing connections for both patterns
        assert len(missing) == 2

        # One for NSG-to-NIC
        nsg_missing = [m for m in missing if m.rule_name == "nsg_to_nic"]
        assert len(nsg_missing) == 1

        # One for Route-Table-to-Subnet
        rt_missing = [m for m in missing if m.rule_name == "route_table_to_subnet"]
        assert len(rt_missing) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
