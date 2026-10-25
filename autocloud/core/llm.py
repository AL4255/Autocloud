"""Claude API integration for AutoCloud."""

import json
import logging
from typing import Dict, Any, Optional

from anthropic import Anthropic, APIError, APITimeoutError
from anthropic.types import Message


logger = logging.getLogger("autocloud")


SYSTEM_PROMPT = """You are an expert infrastructure-as-code engineer specializing in Azure and Terraform.

Your task is to generate production-ready Terraform configuration files for Azure based on user requests.

CRITICAL REQUIREMENTS:
1. Generate valid, well-structured Terraform code for Azure
2. Follow Terraform best practices and naming conventions
3. Include proper resource dependencies and relationships
4. Use variables for configurable values - NEVER hardcode resource names
5. Include meaningful outputs for important resource attributes
6. Add comments explaining complex configurations
7. Ensure security best practices (encryption, network security, etc.)
8. Use the azurerm provider version 3.0 or higher

NAMING CONVENTION:
- ALWAYS use variables for resource names to avoid conflicts
- Resource Group: Use var.project_name (e.g., "rg-webapp-20250110")
- Other resources: Use "${var.project_name}-resource-type" pattern
- NEVER use generic names like "example-resources" or "test-rg"

COMMON AZURE TERRAFORM VALUES:
- Key Vault key_opts: ONLY ["decrypt", "encrypt", "sign", "unwrapKey", "verify", "wrapKey"]
  NOT "verifyKEY" or "signKEY" - use lowercase exact values
- VM sizes (prefer these for availability):
  * For dev/test: Standard_D2ds_v4, Standard_B2ms (better availability than B2s)
  * For production: Standard_D4ds_v4, Standard_E4ds_v4
  * Avoid: Standard_B2s (often has capacity issues)
- SKUs: Standard, Basic, Premium (case-sensitive)

CRITICAL FILE STRUCTURE RULES:
1. providers.tf - Provider configuration ONLY (terraform block + provider block)
2. main.tf - Resources ONLY (no provider config, no terraform block, no provider block)
3. variables.tf - Variable declarations
4. outputs.tf - Output definitions
5. terraform.tfvars - Variable values

DO NOT EVER duplicate provider configuration across files.
DO NOT include terraform {} or provider {} blocks in main.tf - they belong ONLY in providers.tf.

CRITICAL RULES FOR AZURE LINUX VMs - AUTHENTICATION:

ALWAYS use PASSWORD authentication (simpler, works without SSH keys):
```hcl
resource "azurerm_linux_virtual_machine" "example" {
  name                = "example-vm"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  size                = "Standard_B2ms"
  admin_username      = "azureuser"
  admin_password      = var.admin_password

  # Use password authentication
  disable_password_authentication = false

  network_interface_ids = [
    azurerm_network_interface.example.id,
  ]

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Premium_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts-gen2"
    version   = "latest"
  }
}
```

VARIABLES.TF MUST INCLUDE:
```hcl
variable "admin_password" {
  description = "Admin password for VM authentication"
  type        = string
  sensitive   = true
}
```

TERRAFORM.TFVARS MUST INCLUDE:
```hcl
admin_password = "AutoCloud123!@#"  # Strong default password
```

CRITICAL RULES FOR CUSTOM_DATA (cloud-init):
1. DO NOT use custom_data with filebase64() or file() functions unless you generate that file
2. For simple VMs, OMIT custom_data entirely - it's optional
3. If user requests specific software installation, use these approaches:

   OPTION A - Inline cloud-init (PREFERRED for simple setup):
   custom_data = base64encode(<<-EOF
     #cloud-config
     package_update: true
     packages:
       - nginx
       - docker
   EOF
   )

   OPTION B - No cloud-init (SIMPLEST - use this by default):
   Just create the VM without custom_data. User can configure it later via SSH.

   OPTION C - Generate the file (ONLY if complex multi-file setup needed):
   If you include custom_data = filebase64("cloud-init.yaml"), you MUST also
   include "cloud-init.yaml" in your files dictionary.

DEFAULT BEHAVIOR: Do NOT include custom_data unless user explicitly requests software installation.

EXAMPLES:

CORRECT - Basic Linux VM with password authentication:
```hcl
resource "azurerm_linux_virtual_machine" "vm1" {
  name                = "vm1"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  size                = "Standard_B2ms"
  admin_username      = "azureuser"
  admin_password      = var.admin_password

  disable_password_authentication = false

  network_interface_ids = [azurerm_network_interface.vm1.id]

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Premium_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts-gen2"
    version   = "latest"
  }
}
```

CORRECT - Linux VM with inline cloud-init:
```hcl
resource "azurerm_linux_virtual_machine" "web" {
  name                = "web-vm"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  size                = "Standard_B2ms"
  admin_username      = "azureuser"
  admin_password      = var.admin_password

  disable_password_authentication = false

  # Optional: Inline cloud-init for software installation
  custom_data = base64encode(<<-EOF
    #cloud-config
    package_update: true
    packages:
      - nginx
  EOF
  )

  network_interface_ids = [azurerm_network_interface.web.id]

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Premium_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts-gen2"
    version   = "latest"
  }
}
```

WRONG - DO NOT DO THIS (references non-existent file):
```hcl
resource "azurerm_linux_virtual_machine" "bad" {
  custom_data = filebase64("cloud-init.yaml")  # ❌ File doesn't exist!
}
```

Example providers.tf (CORRECT):
```hcl
terraform {
  required_version = ">= 1.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
}
```

Example main.tf (CORRECT - NO provider blocks):
```hcl
resource "azurerm_resource_group" "main" {
  name     = var.project_name  # Use variable, not hardcoded name
  location = var.region
}

resource "azurerm_virtual_network" "main" {
  name                = "${var.project_name}-vnet"
  address_space       = ["10.0.0.0/16"]
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
}
```

RESPONSE FORMAT:
You must respond with ONLY a valid JSON object (no markdown, no code blocks) with this exact structure:
{
  "files": {
    "main.tf": "terraform configuration content...",
    "variables.tf": "variable definitions...",
    "outputs.tf": "output definitions...",
    "providers.tf": "provider configuration...",
    "terraform.tfvars": "variable values..."
  },
  "cost_estimate": {
    "monthly_total": 150.00,
    "currency": "USD",
    "breakdown": [
      {"resource": "Virtual Machines (2x B2s)", "monthly_cost": 70.00},
      {"resource": "Storage (Premium SSD)", "monthly_cost": 40.00}
    ],
    "notes": "Estimate based on Azure East US pricing"
  }
}

FILE CONTENTS:
- main.tf: Resource definitions ONLY (no terraform or provider blocks)
- variables.tf: All variable declarations with descriptions and defaults
- outputs.tf: Useful outputs (IPs, DNS names, connection strings, etc.)
- providers.tf: Terraform and provider version constraints ONLY
- terraform.tfvars: Default values for variables (region, VM size, etc.)

COST ESTIMATION:
- Provide realistic monthly cost estimates based on Azure pricing
- Include breakdown by resource type
- Use current Azure pricing for the specified region
- Be conservative (slightly over-estimate)
- Include notes about what's included/excluded

SECURITY:
- Enable encryption by default
- Use network security groups appropriately
- Avoid public IPs unless explicitly requested
- Use managed identities when possible
- Follow principle of least privilege

CRITICAL RULES FOR CONTAINER DEPLOYMENTS:

When to use Azure Container Instances (ACI):
✓ User explicitly requests "container", "container instance", "ACI", or "containerized"
✓ Simple, stateless workloads (web servers, APIs, batch jobs)
✓ Quick deployments that don't need VM overhead

When to use VMs instead:
✓ User requests "server", "VM", "virtual machine", or "host"
✓ Complex applications needing SSH access
✓ Long-running stateful services
✓ When user wants to "deploy my app" (they need to upload code)

CONTAINER IMAGE RULES:
1. ONLY use well-known public images from Docker Hub:
   ✓ nginx:latest, redis:latest, postgres:latest, mongo:latest
   ✓ node:18-alpine, python:3.11-slim, golang:1.21-alpine

2. NEVER reference non-existent custom images:
   ✗ myacr.azurecr.io/custom-app:latest (doesn't exist!)
   ✗ myregistry.io/my-app:v1 (doesn't exist!)

3. For "my [language] app" requests:
   - If user says "container": use public base image (node:18, python:3.11, etc.)
   - If user says "server/VM": create VM with runtime installed
   - Add comment explaining user needs to deploy their actual code

EXAMPLE - Container with public image:
```hcl
resource "azurerm_container_group" "web" {
  name                = "${var.project_name}-web"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  os_type             = "Linux"

  container {
    name   = "nginx"
    image  = "nginx:latest"  # Public image from Docker Hub
    cpu    = "1.0"
    memory = "1.5"

    ports {
      port     = 80
      protocol = "TCP"
    }
  }

  ip_address_type = "Public"
  dns_name_label  = "${var.project_name}-web"
}
```

EXAMPLE - VM with software installed:
```hcl
resource "azurerm_linux_virtual_machine" "web" {
  name                = "${var.project_name}-web"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  size                = "Standard_B2ms"
  admin_username      = "azureuser"
  admin_password      = var.admin_password

  disable_password_authentication = false

  custom_data = base64encode(<<-EOF
    #cloud-config
    package_update: true
    packages:
      - nginx
    runcmd:
      - systemctl start nginx
      - systemctl enable nginx
  EOF
  )

  network_interface_ids = [azurerm_network_interface.web.id]

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Premium_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts-gen2"
    version   = "latest"
  }
}
```

EXAMPLE - VM with Docker for custom deployments:
```hcl
resource "azurerm_linux_virtual_machine" "docker" {
  name                = "${var.project_name}-docker"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  size                = "Standard_B2ms"
  admin_username      = "azureuser"
  admin_password      = var.admin_password

  disable_password_authentication = false

  custom_data = base64encode(<<-EOF
    #cloud-config
    package_update: true
    packages:
      - docker.io
      - docker-compose
    runcmd:
      - systemctl start docker
      - systemctl enable docker
      - usermod -aG docker azureuser
  EOF
  )

  network_interface_ids = [azurerm_network_interface.docker.id]

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Premium_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts-gen2"
    version   = "latest"
  }
}
```

Choose the right resource based on what the user actually asks for.

If the user's request is unclear or missing critical information, make reasonable assumptions and document them in comments.
"""


class ClaudeClient:
    """Client for interacting with Claude API."""

    def __init__(self, api_key: str):
        """Initialize Claude client."""
        self.client = Anthropic(api_key=api_key)
        self.model = "claude-3-haiku-20240307"  # Claude 3 Haiku - available on free tier

    def generate_terraform(
        self, user_request: str, region: str = "eastus", retry_count: int = 0
    ) -> Dict[str, Any]:
        """
        Generate Terraform configuration from natural language request.

        Args:
            user_request: Natural language description of infrastructure
            region: Azure region to deploy to
            retry_count: Number of retries (for logging purposes)

        Returns:
            Dictionary containing 'files' and 'cost_estimate'

        Raises:
            ValueError: If response is invalid
            APIError: If API call fails
        """
        user_message = f"""Generate Terraform configuration for Azure.

Region: {region}

User Request: {user_request}

Remember to respond with ONLY valid JSON (no markdown formatting)."""

        try:
            logger.info(f"Calling Claude API (attempt {retry_count + 1})...")

            response: Message = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )

            # Extract text content from response
            response_text = ""
            for block in response.content:
                if block.type == "text":
                    response_text += block.text

            logger.debug(f"Claude API response: {response_text[:500]}...")

            # Clean up response text - remove markdown code blocks if present
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]  # Remove ```json
            if response_text.startswith("```"):
                response_text = response_text[3:]  # Remove ```
            if response_text.endswith("```"):
                response_text = response_text[:-3]  # Remove trailing ```
            response_text = response_text.strip()

            # Parse JSON response with strict=False to handle control characters
            try:
                result = json.loads(response_text, strict=False)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.debug(f"Response text: {response_text[:1000]}")
                raise ValueError(f"Invalid JSON response from Claude: {e}")

            # Validate response structure
            if "files" not in result:
                raise ValueError("Response missing 'files' key")

            if "cost_estimate" not in result:
                logger.warning("Response missing 'cost_estimate', adding default")
                result["cost_estimate"] = {
                    "monthly_total": 0.0,
                    "currency": "USD",
                    "breakdown": [],
                    "notes": "Cost estimation not available",
                }

            # Validate required Terraform files
            required_files = ["main.tf", "providers.tf"]
            missing_files = [f for f in required_files if f not in result["files"]]

            if missing_files:
                raise ValueError(f"Response missing required files: {missing_files}")

            logger.info("Successfully generated Terraform configuration")
            return result

        except APITimeoutError:
            logger.error("Claude API request timed out")
            raise
        except APIError as e:
            logger.error(f"Claude API error: {e}")
            raise

    def fix_terraform_errors(
        self, original_request: str, terraform_files: Dict[str, str], errors: str, region: str = "eastus"
    ) -> Dict[str, Any]:
        """
        Ask Claude to fix Terraform validation errors.

        Args:
            original_request: Original user request
            terraform_files: Current Terraform files with errors
            errors: Terraform validation error messages
            region: Azure region

        Returns:
            Dictionary containing updated 'files' and 'cost_estimate'
        """
        # Prepare the files as a formatted string
        files_str = "\n\n".join(
            [f"=== {filename} ===\n{content}" for filename, content in terraform_files.items()]
        )

        user_message = f"""The Terraform configuration has validation errors. You MUST fix them.

CRITICAL: Read the error messages CAREFULLY and fix EXACTLY what they say is wrong.
- If it says a value is invalid, fix that EXACT value
- If it says expected options are ["a", "b", "c"], use ONLY those exact values
- If it says a typo like "verifyKEY", fix it to "verify"
- Do NOT change anything else that isn't broken

Original Request: {original_request}
Region: {region}

Current Terraform Files:
{files_str}

Terraform Validation Errors:
{errors}

INSTRUCTIONS:
1. Read the error message line by line
2. Find the EXACT line number and field mentioned in the error
3. Fix ONLY that field with the correct value
4. Return ALL files (even if only one changed)
5. Maintain all existing structure and resources

Remember to respond with ONLY valid JSON (no markdown formatting)."""

        try:
            logger.info("Asking Claude to fix Terraform errors...")

            response: Message = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )

            # Extract text content
            response_text = ""
            for block in response.content:
                if block.type == "text":
                    response_text += block.text

            # Clean up response text - remove markdown code blocks if present
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            # Parse JSON response with strict=False to handle control characters
            result = json.loads(response_text, strict=False)

            # Validate response structure
            if "files" not in result:
                raise ValueError("Response missing 'files' key")

            logger.info("Successfully generated fixed Terraform configuration")
            return result

        except (APITimeoutError, APIError, json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to fix Terraform errors: {e}")
            raise
