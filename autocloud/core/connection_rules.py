"""
Azure Resource Connection Rules

This file defines the patterns for detecting and fixing missing Azure resource associations.

WHAT ARE ASSOCIATION RESOURCES?
Azure uses explicit "glue" resources to connect primary resources to their targets.
Example: A Load Balancer doesn't automatically connect to VMs - you need association resources
to create the connection.

HOW THIS WORKS:
1. Each rule defines a pattern: primary + targets → required associations
2. The connection fixer detects when pattern exists but associations are missing
3. It generates the missing Terraform code using templates
4. It injects the code into main.tf

ADDING NEW RULES:
When you discover a new missing connection pattern:
1. Identify: primary resource type, target resource type(s), association resource type(s)
2. Research: Azure/Terraform docs for correct association syntax
3. Add rule: Copy existing rule structure, modify for your pattern
4. Test: Deploy infrastructure to verify it works

Azure Documentation:
https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs
"""

from typing import Dict, List, Any
from dataclasses import dataclass


@dataclass
class ConnectionRule:
    """
    Represents a single connection rule.

    Attributes:
        name: Unique identifier for this rule
        description: Human-readable explanation
        primary: Primary resource type (e.g., "azurerm_lb")
        targets: List of target resource types (e.g., ["azurerm_network_interface"])
        required_connections: List of association definitions
        enabled: Whether this rule is active (for debugging)
    """
    name: str
    description: str
    primary: str
    targets: List[str]
    required_connections: List[Dict[str, Any]]
    enabled: bool = True


# ==============================================================================
# RULE 1: NETWORK SECURITY GROUP (SIMPLE - 1:1 ASSOCIATION)
# ==============================================================================

NSG_TO_NIC_RULE = ConnectionRule(
    name="nsg_to_nic",
    description="""
    Connect Network Security Group to Network Interface.

    SCENARIO:
    User asks for "VMs with firewall rules" or "VMs with NSG"
    LLM generates azurerm_network_security_group and azurerm_network_interface
    BUT FORGETS: The association that applies the NSG to each NIC

    AZURE PATTERN:
    - Primary: NSG (firewall rules)
    - Target: NIC (network card for VM)
    - Association: Explicit binding (one per NIC)

    WITHOUT THIS:
    NSG rules exist but don't apply to any traffic!

    TERRAFORM DOCS:
    https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/network_interface_security_group_association
    """,

    primary="azurerm_network_security_group",
    targets=["azurerm_network_interface"],

    required_connections=[
        {
            # What association resource to create
            "type": "azurerm_network_interface_security_group_association",

            # How many? "single" = one total, "per_target" = one per NIC
            "count": "per_target",

            # Terraform template (using Python string formatting)
            # Available variables:
            #   {assoc_name} - generated name for this association
            #   {primary_name} - name of the NSG
            #   {target_name} - name of the NIC
            "template": '''resource "azurerm_network_interface_security_group_association" "{assoc_name}" {{
  network_interface_id      = azurerm_network_interface.{target_name}.id
  network_security_group_id = azurerm_network_security_group.{primary_name}.id
}}''',

            # How to generate the association name
            # Pattern: {primary}_{target}_nsg_assoc
            "name_pattern": "{primary_name}_{target_name}_nsg_assoc",

            # Additional context for error messages
            "missing_message": "Network Security Group '{primary_name}' is not associated with NIC '{target_name}'"
        }
    ]
)


# ==============================================================================
# RULE 2: ROUTE TABLE (MEDIUM - 1:1 WITH SUBNET TARGET)
# ==============================================================================

ROUTE_TABLE_TO_SUBNET_RULE = ConnectionRule(
    name="route_table_to_subnet",
    description="""
    Connect Route Table to Subnet.

    SCENARIO:
    User asks for "VMs with custom routing" or "route traffic through firewall"
    LLM generates azurerm_route_table and azurerm_subnet
    BUT FORGETS: The association that applies routes to the subnet

    AZURE PATTERN:
    - Primary: Route Table (custom routing rules)
    - Target: Subnet (network segment)
    - Association: Explicit binding (one per subnet)

    WITHOUT THIS:
    Route table exists but subnet uses default Azure routing!

    TERRAFORM DOCS:
    https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/subnet_route_table_association
    """,

    primary="azurerm_route_table",
    targets=["azurerm_subnet"],

    required_connections=[
        {
            "type": "azurerm_subnet_route_table_association",
            "count": "per_target",

            "template": '''resource "azurerm_subnet_route_table_association" "{assoc_name}" {{
  subnet_id      = azurerm_subnet.{target_name}.id
  route_table_id = azurerm_route_table.{primary_name}.id
}}''',

            "name_pattern": "{primary_name}_{target_name}_rt_assoc",
            "missing_message": "Route Table '{primary_name}' is not associated with Subnet '{target_name}'"
        }
    ]
)


# ==============================================================================
# RULE 3: LOAD BALANCER (COMPLEX - 4 ASSOCIATION TYPES)
# ==============================================================================

LOAD_BALANCER_TO_VMS_RULE = ConnectionRule(
    name="load_balancer_to_vms",
    description="""
    Connect Load Balancer to Virtual Machines (via NICs).

    SCENARIO:
    User asks for "2 VMs with load balancer"
    LLM generates azurerm_lb and azurerm_network_interface resources
    BUT FORGETS: The 4 association resources that actually connect them!

    AZURE PATTERN (COMPLEX):
    - Primary: Load Balancer
    - Targets: Network Interfaces (NICs attached to VMs)
    - Associations: FOUR separate resources needed:
      1. Backend Address Pool (container for VMs)
      2. NIC-to-Pool Associations (one per VM)
      3. Health Probe (monitors backend health)
      4. Load Balancing Rule (defines traffic routing)

    WHY SO COMPLEX?
    Azure separates concerns:
    - Backend pool = "which VMs are available"
    - Associations = "add this specific VM to the pool"
    - Health probe = "how to check if VM is healthy"
    - LB rule = "route traffic from frontend:80 to backend:80 if healthy"

    WITHOUT THIS:
    Load balancer exists, VMs exist, but NO TRAFFIC FLOWS!

    TERRAFORM DOCS:
    - Backend Pool: https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/lb_backend_address_pool
    - NIC Association: https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/network_interface_backend_address_pool_association
    - Health Probe: https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/lb_probe
    - LB Rule: https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/lb_rule
    """,

    primary="azurerm_lb",
    targets=["azurerm_network_interface"],

    required_connections=[
        # ======================================================================
        # ASSOCIATION 1: Backend Address Pool (ONE per LB)
        # ======================================================================
        {
            "type": "azurerm_lb_backend_address_pool",
            "count": "single",  # Only ONE pool needed per LB

            "template": '''resource "azurerm_lb_backend_address_pool" "{assoc_name}" {{
  loadbalancer_id = azurerm_lb.{primary_name}.id
  name            = "backend-pool"
}}''',

            "name_pattern": "{primary_name}_backend_pool",
            "missing_message": "Load Balancer '{primary_name}' is missing backend address pool",

            # This association is referenced by others (NIC associations and LB rule)
            "is_dependency": True
        },

        # ======================================================================
        # ASSOCIATION 2: NIC-to-Pool Associations (ONE per NIC/VM)
        # ======================================================================
        {
            "type": "azurerm_network_interface_backend_address_pool_association",
            "count": "per_target",  # One per NIC

            # NOTE: This references the backend pool created above
            # We use {primary_name}_backend_pool as the pool resource name
            "template": '''resource "azurerm_network_interface_backend_address_pool_association" "{assoc_name}" {{
  network_interface_id    = azurerm_network_interface.{target_name}.id
  ip_configuration_name   = "internal"
  backend_address_pool_id = azurerm_lb_backend_address_pool.{primary_name}_backend_pool.id
}}''',

            "name_pattern": "{primary_name}_{target_name}_pool_assoc",
            "missing_message": "NIC '{target_name}' is not associated with Load Balancer '{primary_name}' backend pool",

            # This depends on the backend pool existing
            "depends_on": ["azurerm_lb_backend_address_pool"]
        },

        # ======================================================================
        # ASSOCIATION 3: Health Probe (ONE per LB)
        # ======================================================================
        {
            "type": "azurerm_lb_probe",
            "count": "single",

            # Health check configuration
            # Checks HTTP GET / on port 80 every 15 seconds
            "template": '''resource "azurerm_lb_probe" "{assoc_name}" {{
  loadbalancer_id = azurerm_lb.{primary_name}.id
  name            = "http-health-check"
  protocol        = "Http"
  port            = 80
  request_path    = "/"
  interval_in_seconds = 15
  number_of_probes    = 2
}}''',

            "name_pattern": "{primary_name}_health_probe",
            "missing_message": "Load Balancer '{primary_name}' is missing health probe",
            "is_dependency": True
        },

        # ======================================================================
        # ASSOCIATION 4: Load Balancing Rule (ONE per LB)
        # ======================================================================
        {
            "type": "azurerm_lb_rule",
            "count": "single",

            # This references BOTH the backend pool and health probe
            # NOTE: frontend_ip_configuration_name must match the name in azurerm_lb
            # We use a common default "public-ip" but this might need to be dynamic
            "template": '''resource "azurerm_lb_rule" "{assoc_name}" {{
  loadbalancer_id                = azurerm_lb.{primary_name}.id
  name                           = "http-rule"
  protocol                       = "Tcp"
  frontend_port                  = 80
  backend_port                   = 80
  frontend_ip_configuration_name = "public-ip"
  backend_address_pool_ids       = [azurerm_lb_backend_address_pool.{primary_name}_backend_pool.id]
  probe_id                       = azurerm_lb_probe.{primary_name}_health_probe.id
  disable_outbound_snat          = false
  enable_tcp_reset               = true
}}''',

            "name_pattern": "{primary_name}_lb_rule",
            "missing_message": "Load Balancer '{primary_name}' is missing load balancing rule",

            # This depends on both backend pool and health probe
            "depends_on": ["azurerm_lb_backend_address_pool", "azurerm_lb_probe"]
        }
    ]
)


# ==============================================================================
# MASTER RULES REGISTRY
# ==============================================================================

# This is the main dictionary that the connection fixer will use
# Add new rules here as you discover missing connection patterns
AZURE_CONNECTION_RULES = {
    "nsg_to_nic": NSG_TO_NIC_RULE,
    "route_table_to_subnet": ROUTE_TABLE_TO_SUBNET_RULE,
    "load_balancer_to_vms": LOAD_BALANCER_TO_VMS_RULE,
}


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def get_enabled_rules() -> Dict[str, ConnectionRule]:
    """
    Get all enabled connection rules.

    Returns:
        Dictionary of rule_name -> ConnectionRule for enabled rules only
    """
    return {name: rule for name, rule in AZURE_CONNECTION_RULES.items() if rule.enabled}


def get_rule_by_name(rule_name: str) -> ConnectionRule:
    """
    Get a specific rule by name.

    Args:
        rule_name: The rule identifier

    Returns:
        ConnectionRule instance

    Raises:
        KeyError: If rule doesn't exist
    """
    return AZURE_CONNECTION_RULES[rule_name]


def disable_rule(rule_name: str) -> None:
    """
    Temporarily disable a rule (useful for debugging).

    Args:
        rule_name: The rule to disable
    """
    if rule_name in AZURE_CONNECTION_RULES:
        AZURE_CONNECTION_RULES[rule_name].enabled = False


def enable_rule(rule_name: str) -> None:
    """
    Re-enable a disabled rule.

    Args:
        rule_name: The rule to enable
    """
    if rule_name in AZURE_CONNECTION_RULES:
        AZURE_CONNECTION_RULES[rule_name].enabled = True


# ==============================================================================
# HOW TO ADD A NEW RULE
# ==============================================================================

"""
EXAMPLE: Adding Application Gateway to Backend Pool rule

1. Identify the pattern from Azure deployment failure or Terraform docs:
   - Primary: azurerm_application_gateway
   - Targets: azurerm_network_interface or azurerm_virtual_machine
   - Associations: azurerm_application_gateway_backend_address_pool

2. Research the Terraform syntax:
   Visit: https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/application_gateway_backend_address_pool

3. Create the rule:

APP_GATEWAY_RULE = ConnectionRule(
    name="app_gateway_to_backend",
    description="Connect Application Gateway to backend VMs",
    primary="azurerm_application_gateway",
    targets=["azurerm_network_interface"],
    required_connections=[
        {
            "type": "azurerm_application_gateway_backend_address_pool",
            "count": "single",
            "template": '''resource "azurerm_application_gateway_backend_address_pool" "{assoc_name}" {{
  name                = "backend-pool"
  application_gateway_id = azurerm_application_gateway.{primary_name}.id
}}''',
            "name_pattern": "{primary_name}_backend_pool",
            "missing_message": "Application Gateway '{primary_name}' missing backend pool"
        }
    ]
)

4. Add to AZURE_CONNECTION_RULES:

AZURE_CONNECTION_RULES["app_gateway_to_backend"] = APP_GATEWAY_RULE

5. Test:

autocloud deploy "create app gateway with 2 backend VMs"

6. Verify the generated main.tf includes the association resource
"""
