"""Terraform code generation and file management."""

import logging
from pathlib import Path
from typing import Dict, Any, Optional

from autocloud.core.llm import ClaudeClient
from autocloud.core.connection_fixer import create_fixer
from autocloud.utils.logger import get_project_logger


logger = logging.getLogger("autocloud")


class TerraformGenerator:
    """Handles Terraform code generation and file writing."""

    def __init__(self, project_dir: Path, api_key: str, ssh_public_key: Optional[str] = None):
        """
        Initialize Terraform generator.

        Args:
            project_dir: Directory to write Terraform files to
            api_key: Anthropic API key
            ssh_public_key: SSH public key for Linux VM authentication (optional)
        """
        self.project_dir = project_dir
        self.project_dir.mkdir(parents=True, exist_ok=True)

        self.claude_client = ClaudeClient(api_key)
        self.project_logger = get_project_logger(project_dir, "generation")
        self.connection_fixer = create_fixer()  # Initialize connection fixer
        self.ssh_public_key = ssh_public_key

    def generate(self, user_request: str, region: str = "eastus") -> Dict[str, Any]:
        """
        Generate Terraform configuration from user request.

        NEW: Now includes automatic connection fixing!
        After LLM generates initial Terraform, this method:
        1. Detects missing Azure resource associations
        2. Automatically injects required connection resources
        3. Logs what was fixed for transparency

        Args:
            user_request: Natural language infrastructure request
            region: Azure region to deploy to

        Returns:
            Dictionary with 'files' and 'cost_estimate'
        """
        logger.info("Generating Terraform configuration...")
        self.project_logger.info(f"User request: {user_request}")
        self.project_logger.info(f"Region: {region}")

        try:
            # STEP 1: LLM generates initial Terraform
            result = self.claude_client.generate_terraform(user_request, region)

            # Log the generation
            self.project_logger.info("Successfully generated Terraform configuration")
            self.project_logger.debug(f"Files generated: {list(result['files'].keys())}")

            # STEP 2: Fix missing connections
            if "main.tf" in result["files"]:
                logger.info("🔧 Checking for missing resource connections...")

                fixed_content, descriptions = self.connection_fixer.fix_terraform(
                    result["files"]["main.tf"]
                )

                if descriptions:
                    # Connections were fixed!
                    logger.info(f"✅ Auto-fixed {len(descriptions)} missing connection(s):")
                    for desc in descriptions:
                        logger.info(f"   • {desc}")

                    self.project_logger.info(f"Auto-fixed {len(descriptions)} missing connections")
                    for desc in descriptions:
                        self.project_logger.info(f"  {desc}")

                    # Update the main.tf with fixed version
                    result["files"]["main.tf"] = fixed_content
                else:
                    logger.info("✅ No missing connections detected")

            return result

        except Exception as e:
            self.project_logger.error(f"Failed to generate Terraform: {e}")
            raise

    def write_files(self, files: Dict[str, str]) -> None:
        """
        Write Terraform files to project directory.

        Also writes terraform.tfvars with SSH public key if available.

        Args:
            files: Dictionary mapping filenames to content
        """
        logger.info(f"Writing {len(files)} Terraform files...")

        for filename, content in files.items():
            # Skip if content is None or empty
            if content is None:
                logger.warning(f"Skipping {filename} - content is None")
                continue

            if not isinstance(content, str):
                logger.warning(f"Skipping {filename} - content is not a string: {type(content)}")
                continue

            file_path = self.project_dir / filename

            with open(file_path, "w") as f:
                f.write(content)

            self.project_logger.info(f"Wrote file: {filename} ({len(content)} bytes)")
            logger.debug(f"Created: {file_path}")

        # Add SSH public key to terraform.tfvars if available
        if self.ssh_public_key:
            tfvars_path = self.project_dir / "terraform.tfvars"

            # Read existing tfvars or create new
            existing_content = ""
            if tfvars_path.exists():
                existing_content = tfvars_path.read_text()

            # Check if ssh_public_key is already defined
            if "ssh_public_key" not in existing_content:
                # Escape the SSH key for HCL (handle special characters)
                escaped_key = self.ssh_public_key.replace('\\', '\\\\').replace('"', '\\"')
                ssh_key_line = f'\nssh_public_key = "{escaped_key}"\n'

                with open(tfvars_path, "a") as f:
                    f.write(ssh_key_line)

                self.project_logger.info("Added SSH public key to terraform.tfvars")
                logger.info("✓ SSH public key added to terraform.tfvars")

        logger.info("All Terraform files written successfully")

    def regenerate_with_fixes(
        self, original_request: str, current_files: Dict[str, str], errors: str, region: str = "eastus"
    ) -> Dict[str, Any]:
        """
        Ask Claude to fix Terraform errors and regenerate files.

        Args:
            original_request: Original user request
            current_files: Current Terraform files with errors
            errors: Terraform validation errors
            region: Azure region

        Returns:
            Dictionary with updated 'files' and 'cost_estimate'
        """
        logger.info("Requesting fixes for Terraform errors...")
        self.project_logger.info("Requesting Terraform error fixes")
        self.project_logger.debug(f"Errors:\n{errors}")

        try:
            result = self.claude_client.fix_terraform_errors(
                original_request, current_files, errors, region
            )

            self.project_logger.info("Successfully generated fixed Terraform configuration")

            # CRITICAL FIX: Run connection fixer on retry-fixed code too!
            # The LLM might have fixed validation errors but still missed connections
            if "main.tf" in result["files"]:
                logger.info("🔧 Re-checking for missing connections after error fix...")

                fixed_content, descriptions = self.connection_fixer.fix_terraform(
                    result["files"]["main.tf"]
                )

                if descriptions:
                    logger.info(f"✅ Re-applied connection fixer: {len(descriptions)} missing connection(s)")
                    for desc in descriptions:
                        logger.info(f"   • {desc}")

                    self.project_logger.info(f"Re-applied connection fixer after retry: {len(descriptions)} fixes")

                    # Update the main.tf with re-fixed version
                    result["files"]["main.tf"] = fixed_content
                else:
                    logger.info("✅ No additional missing connections after retry")

            return result

        except Exception as e:
            self.project_logger.error(f"Failed to fix Terraform errors: {e}")
            raise

    def read_current_files(self) -> Dict[str, str]:
        """
        Read all Terraform files from project directory.

        Returns:
            Dictionary mapping filenames to content
        """
        files = {}
        tf_extensions = [".tf", ".tfvars"]

        for file_path in self.project_dir.iterdir():
            if file_path.is_file() and any(file_path.name.endswith(ext) for ext in tf_extensions):
                with open(file_path, "r") as f:
                    files[file_path.name] = f.read()

        return files
