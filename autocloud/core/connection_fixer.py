"""
Azure Connection Fixer Engine

This module detects missing Azure resource associations and generates the required Terraform code.

ARCHITECTURE:
1. Parse Terraform HCL to extract resource types and names
2. Apply connection rules to detect missing associations
3. Generate Terraform code from templates
4. Inject generated code into main.tf

USAGE:
    from autocloud.core.connection_fixer import AzureConnectionFixer
    from autocloud.core.connection_rules import AZURE_CONNECTION_RULES

    fixer = AzureConnectionFixer(AZURE_CONNECTION_RULES)
    resources = fixer.parse_terraform_resources(main_tf_content)
    missing = fixer.detect_missing_connections(resources)

    if missing:
        fixed_tf = fixer.inject_connections(main_tf_content, missing)
"""

import re
import logging
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass

from autocloud.core.connection_rules import ConnectionRule, get_enabled_rules


logger = logging.getLogger("autocloud")


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class MissingConnection:
    """
    Represents a detected missing connection that needs to be fixed.

    Attributes:
        rule_name: Which rule detected this missing connection
        primary_resource: Type and name of primary resource (e.g., ("azurerm_lb", "web_lb"))
        target_resources: List of (type, name) tuples for targets
        association_config: The connection rule config that defines how to fix it
        description: Human-readable explanation of what's missing
    """
    rule_name: str
    primary_resource: Tuple[str, str]  # (type, name)
    target_resources: List[Tuple[str, str]]  # [(type, name), ...]
    association_config: Dict
    description: str


# ==============================================================================
# MAIN FIXER CLASS
# ==============================================================================

class AzureConnectionFixer:
    """
    Detects and fixes missing Azure resource associations.

    This class:
    1. Parses Terraform to find existing resources
    2. Applies connection rules to detect missing associations
    3. Generates Terraform for missing connections
    4. Injects generated code into main.tf
    """

    def __init__(self, connection_rules: Dict[str, ConnectionRule]):
        """
        Initialize the connection fixer.

        Args:
            connection_rules: Dictionary of rule_name -> ConnectionRule
        """
        self.rules = connection_rules
        logger.info(f"Connection fixer initialized with {len(self.rules)} rules")

    # ==========================================================================
    # PHASE 1: TERRAFORM PARSING
    # ==========================================================================

    def parse_terraform_resources(self, terraform_content: str) -> Dict[str, List[str]]:
        """
        Extract all resource types and names from Terraform HCL.

        TERRAFORM SYNTAX:
            resource "TYPE" "NAME" {
              config...
            }

        EXAMPLE INPUT:
            resource "azurerm_lb" "web_lb" {
              name = "web-lb"
            }

            resource "azurerm_network_interface" "vm1_nic" {
              name = "vm1-nic"
            }

            resource "azurerm_network_interface" "vm2_nic" {
              name = "vm2-nic"
            }

        EXAMPLE OUTPUT:
            {
                "azurerm_lb": ["web_lb"],
                "azurerm_network_interface": ["vm1_nic", "vm2_nic"]
            }

        REGEX PATTERN BREAKDOWN:
            resource        - Literal word "resource"
            \s+             - One or more whitespace characters
            "([^"]+)"       - Capture group 1: TYPE (anything in quotes)
            \s+             - Whitespace
            "([^"]+)"       - Capture group 2: NAME (anything in quotes)
            \s*             - Optional whitespace
            \{              - Opening brace

        Args:
            terraform_content: Raw Terraform HCL content

        Returns:
            Dictionary mapping resource_type -> [list of resource names]
        """
        resources: Dict[str, List[str]] = {}

        # Regex to match: resource "TYPE" "NAME" {
        pattern = r'resource\s+"([^"]+)"\s+"([^"]+)"\s*\{'

        matches = re.finditer(pattern, terraform_content)

        for match in matches:
            resource_type = match.group(1)  # e.g., "azurerm_lb"
            resource_name = match.group(2)  # e.g., "web_lb"

            # Add to dictionary (create list if first time seeing this type)
            if resource_type not in resources:
                resources[resource_type] = []

            resources[resource_type].append(resource_name)

        logger.debug(f"Parsed {sum(len(v) for v in resources.values())} resources across {len(resources)} types")

        return resources

    # ==========================================================================
    # PHASE 2: DETECTION ENGINE
    # ==========================================================================

    def detect_missing_connections(
        self,
        resources: Dict[str, List[str]]
    ) -> List[MissingConnection]:
        """
        Detect missing connection resources by applying all enabled rules.

        ALGORITHM:
            For each connection rule:
                1. Check if pattern applies (primary + targets exist)
                2. Check if required associations exist
                3. If missing, create MissingConnection record

        EXAMPLE:
            Input resources:
                {
                    "azurerm_lb": ["web_lb"],
                    "azurerm_network_interface": ["vm1_nic", "vm2_nic"]
                }

            Rule: load_balancer_to_vms
            - Primary: azurerm_lb ✅ Found
            - Targets: azurerm_network_interface ✅ Found (2 NICs)
            - Required: azurerm_lb_backend_address_pool ❌ Missing
            - Required: azurerm_network_interface_backend_address_pool_association ❌ Missing
            - Required: azurerm_lb_probe ❌ Missing
            - Required: azurerm_lb_rule ❌ Missing

            Result: 4 MissingConnection objects created

        Args:
            resources: Parsed resources from parse_terraform_resources()

        Returns:
            List of MissingConnection objects describing what needs to be fixed
        """
        missing_connections: List[MissingConnection] = []

        # Get only enabled rules
        enabled_rules = get_enabled_rules()

        logger.info(f"Checking {len(enabled_rules)} connection rules...")

        for rule_name, rule in enabled_rules.items():
            logger.debug(f"Evaluating rule: {rule_name}")

            # STEP 1: Does this pattern apply?
            # Check if primary resource exists
            if rule.primary not in resources:
                logger.debug(f"  ❌ Primary '{rule.primary}' not found, skipping")
                continue

            # Check if any target resources exist
            found_targets = []
            for target_type in rule.targets:
                if target_type in resources:
                    for target_name in resources[target_type]:
                        found_targets.append((target_type, target_name))

            if not found_targets:
                logger.debug(f"  ❌ No target resources found, skipping")
                continue

            # Pattern applies! We have primary + targets
            primary_names = resources[rule.primary]
            logger.info(f"  ✅ Pattern detected: {rule.primary} + {len(found_targets)} targets")

            # STEP 2: Check each required association
            for primary_name in primary_names:
                for assoc_config in rule.required_connections:
                    assoc_type = assoc_config["type"]

                    # Is this association type missing?
                    if assoc_type not in resources:
                        # Missing! Create a MissingConnection record
                        missing = MissingConnection(
                            rule_name=rule_name,
                            primary_resource=(rule.primary, primary_name),
                            target_resources=found_targets,
                            association_config=assoc_config,
                            description=self._build_description(
                                rule_name,
                                rule.primary,
                                primary_name,
                                assoc_type,
                                found_targets
                            )
                        )

                        missing_connections.append(missing)
                        logger.info(f"    🔧 Missing: {assoc_type}")

        if missing_connections:
            logger.warning(f"Found {len(missing_connections)} missing connections")
        else:
            logger.info("✅ All connection rules satisfied")

        return missing_connections

    def _build_description(
        self,
        rule_name: str,
        primary_type: str,
        primary_name: str,
        assoc_type: str,
        targets: List[Tuple[str, str]]
    ) -> str:
        """
        Build human-readable description of missing connection.

        Args:
            rule_name: Name of the rule
            primary_type: Resource type of primary
            primary_name: Resource name of primary
            assoc_type: Association resource type that's missing
            targets: List of target (type, name) tuples

        Returns:
            Descriptive string for logging/debugging
        """
        target_summary = f"{len(targets)} {targets[0][0]}"

        return (
            f"[{rule_name}] Missing {assoc_type} to connect "
            f"{primary_type}.{primary_name} with {target_summary}"
        )

    # ==========================================================================
    # PHASE 3: TERRAFORM GENERATION
    # ==========================================================================

    def generate_connection_terraform(
        self,
        missing: MissingConnection
    ) -> List[str]:
        """
        Generate Terraform code for a missing connection.

        ALGORITHM:
            1. Get the template from association_config
            2. Determine count (single vs per_target)
            3. For each resource to create:
                a. Generate resource name from name_pattern
                b. Fill in template placeholders
                c. Return formatted Terraform code

        EXAMPLE (Load Balancer Backend Pool):
            Input:
                missing.primary_resource = ("azurerm_lb", "web_lb")
                missing.association_config = {
                    "type": "azurerm_lb_backend_address_pool",
                    "count": "single",
                    "template": 'resource "azurerm_lb_backend_address_pool" "{assoc_name}" {...}',
                    "name_pattern": "{primary_name}_backend_pool"
                }

            Output:
                [
                    'resource "azurerm_lb_backend_address_pool" "web_lb_backend_pool" {\n  ...\n}'
                ]

        EXAMPLE (NIC-to-Pool Association):
            Input:
                missing.primary_resource = ("azurerm_lb", "web_lb")
                missing.target_resources = [
                    ("azurerm_network_interface", "vm1_nic"),
                    ("azurerm_network_interface", "vm2_nic")
                ]
                missing.association_config = {
                    "count": "per_target",
                    "template": '...',
                    "name_pattern": "{primary_name}_{target_name}_pool_assoc"
                }

            Output:
                [
                    'resource "..." "web_lb_vm1_nic_pool_assoc" {...}',
                    'resource "..." "web_lb_vm2_nic_pool_assoc" {...}'
                ]

        Args:
            missing: MissingConnection describing what to generate

        Returns:
            List of Terraform resource blocks as strings
        """
        generated_resources: List[str] = []

        assoc_config = missing.association_config
        primary_type, primary_name = missing.primary_resource

        template = assoc_config["template"]
        count_mode = assoc_config["count"]
        name_pattern = assoc_config["name_pattern"]

        if count_mode == "single":
            # Generate ONE resource total
            assoc_name = name_pattern.format(
                primary_name=primary_name,
                target_name=""  # Not used for single-count resources
            )

            terraform_code = template.format(
                assoc_name=assoc_name,
                primary_name=primary_name,
                target_name=""  # Not used
            )

            generated_resources.append(terraform_code)
            logger.debug(f"Generated single resource: {assoc_name}")

        elif count_mode == "per_target":
            # Generate ONE resource PER target
            for target_type, target_name in missing.target_resources:
                assoc_name = name_pattern.format(
                    primary_name=primary_name,
                    target_name=target_name
                )

                terraform_code = template.format(
                    assoc_name=assoc_name,
                    primary_name=primary_name,
                    target_name=target_name
                )

                generated_resources.append(terraform_code)
                logger.debug(f"Generated per-target resource: {assoc_name}")

        else:
            logger.error(f"Unknown count mode: {count_mode}")

        return generated_resources

    # ==========================================================================
    # PHASE 4: INJECTION ENGINE
    # ==========================================================================

    def inject_connections(
        self,
        main_tf_content: str,
        missing_connections: List[MissingConnection]
    ) -> str:
        """
        Inject generated connection resources into main.tf.

        STRATEGY:
            1. Sort missing connections by dependency order
            2. Generate Terraform for each
            3. Add header comment explaining what was injected
            4. Append to end of main.tf

        DEPENDENCY SORTING:
            Resources with "is_dependency": True go first
            Resources with "depends_on": [...] go after their dependencies

            Example order for Load Balancer:
                1. azurerm_lb_backend_address_pool (is_dependency)
                2. azurerm_lb_probe (is_dependency)
                3. azurerm_network_interface_backend_address_pool_association (depends_on pool)
                4. azurerm_lb_rule (depends_on pool + probe)

        Args:
            main_tf_content: Original Terraform main.tf content
            missing_connections: List of MissingConnection to fix

        Returns:
            Modified main.tf with injected connection resources
        """
        if not missing_connections:
            return main_tf_content

        logger.info(f"Injecting {len(missing_connections)} missing connections...")

        # Sort by dependency order
        sorted_connections = self._sort_by_dependencies(missing_connections)

        # Generate header
        injection_header = self._build_injection_header(sorted_connections)

        # Generate all Terraform code
        all_terraform: List[str] = []

        for missing in sorted_connections:
            terraform_blocks = self.generate_connection_terraform(missing)
            all_terraform.extend(terraform_blocks)

        # Build injection section
        injection = "\n\n" + injection_header + "\n\n"
        injection += "\n\n".join(all_terraform)
        injection += "\n"

        # Append to main.tf
        modified_content = main_tf_content + injection

        logger.info(f"✅ Injected {len(all_terraform)} connection resources")

        return modified_content

    def _sort_by_dependencies(
        self,
        missing_connections: List[MissingConnection]
    ) -> List[MissingConnection]:
        """
        Sort missing connections by dependency order.

        Resources marked as "is_dependency": True go first.
        Resources with "depends_on" go after their dependencies.

        This ensures generated Terraform references exist before being used.

        Args:
            missing_connections: Unsorted list

        Returns:
            Sorted list with dependencies first
        """
        dependencies_first = []
        regular = []

        for mc in missing_connections:
            if mc.association_config.get("is_dependency", False):
                dependencies_first.append(mc)
            else:
                regular.append(mc)

        # Dependencies first, then regular
        return dependencies_first + regular

    def _build_injection_header(
        self,
        missing_connections: List[MissingConnection]
    ) -> str:
        """
        Build a header comment explaining what was auto-injected.

        Args:
            missing_connections: List of what's being fixed

        Returns:
            Multi-line comment string
        """
        # Group by rule
        by_rule: Dict[str, List[MissingConnection]] = {}
        for mc in missing_connections:
            if mc.rule_name not in by_rule:
                by_rule[mc.rule_name] = []
            by_rule[mc.rule_name].append(mc)

        header_lines = [
            "# " + "=" * 78,
            "# AUTO-GENERATED BY AUTOCLOUD CONNECTION FIXER",
            "# " + "=" * 78,
            "#",
            "# The following resources were automatically added to fix missing connections.",
            "# This ensures infrastructure resources are properly associated.",
            "#"
        ]

        for rule_name, mcs in by_rule.items():
            header_lines.append(f"# Rule: {rule_name}")
            header_lines.append(f"#   Generated {len(mcs)} connection resource(s)")

        header_lines.extend([
            "#",
            "# " + "=" * 78
        ])

        return "\n".join(header_lines)

    # ==========================================================================
    # CONVENIENCE METHOD
    # ==========================================================================

    def fix_terraform(self, main_tf_content: str) -> Tuple[str, List[str]]:
        """
        One-shot method to detect and fix all missing connections.

        This is a convenience wrapper around the full pipeline:
            1. Parse resources
            2. Detect missing connections
            3. Generate Terraform
            4. Inject into main.tf

        Args:
            main_tf_content: Original Terraform content

        Returns:
            Tuple of (modified_content, list_of_descriptions)
        """
        # Parse
        resources = self.parse_terraform_resources(main_tf_content)

        # Detect
        missing = self.detect_missing_connections(resources)

        if not missing:
            logger.info("No missing connections detected")
            return main_tf_content, []

        # Collect descriptions for logging
        descriptions = [m.description for m in missing]

        # Inject
        fixed_content = self.inject_connections(main_tf_content, missing)

        return fixed_content, descriptions


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def create_fixer() -> AzureConnectionFixer:
    """
    Factory function to create a connection fixer with default rules.

    Returns:
        Initialized AzureConnectionFixer
    """
    from autocloud.core.connection_rules import AZURE_CONNECTION_RULES
    return AzureConnectionFixer(AZURE_CONNECTION_RULES)
