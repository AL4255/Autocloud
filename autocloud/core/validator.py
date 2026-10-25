"""Terraform validation with self-healing retry logic."""

import logging
import subprocess
from pathlib import Path
from typing import Tuple, Optional, Dict, Any

from autocloud.core.generator import TerraformGenerator
from autocloud.utils.logger import get_project_logger


logger = logging.getLogger("autocloud")


class TerraformValidator:
    """Validates Terraform configuration with auto-healing."""

    MAX_RETRIES = 3

    def __init__(self, project_dir: Path, generator: Optional[TerraformGenerator] = None):
        """
        Initialize Terraform validator.

        Args:
            project_dir: Directory containing Terraform files
            generator: TerraformGenerator instance for auto-healing (optional)
        """
        self.project_dir = project_dir
        self.generator = generator
        self.project_logger = get_project_logger(project_dir, "validation")

    def terraform_init(self) -> Tuple[bool, str]:
        """
        Run terraform init.

        Returns:
            Tuple of (success, output)
        """
        logger.info("Running terraform init...")
        self.project_logger.info("Running terraform init")

        try:
            result = subprocess.run(
                ["terraform", "init"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            self.project_logger.debug(f"terraform init output:\n{result.stdout}")

            if result.returncode != 0:
                error_output = result.stderr or result.stdout
                self.project_logger.error(f"terraform init failed:\n{error_output}")
                return False, error_output

            logger.info("terraform init completed successfully")
            return True, result.stdout

        except subprocess.TimeoutExpired:
            error_msg = "terraform init timed out after 5 minutes"
            logger.error(error_msg)
            self.project_logger.error(error_msg)
            return False, error_msg

        except FileNotFoundError:
            error_msg = "terraform command not found. Please install Terraform."
            logger.error(error_msg)
            self.project_logger.error(error_msg)
            return False, error_msg

        except Exception as e:
            error_msg = f"Unexpected error during terraform init: {e}"
            logger.error(error_msg)
            self.project_logger.error(error_msg)
            return False, str(e)

    def terraform_validate(self) -> Tuple[bool, str]:
        """
        Run terraform validate.

        Returns:
            Tuple of (success, output)
        """
        logger.info("Running terraform validate...")
        self.project_logger.info("Running terraform validate")

        try:
            result = subprocess.run(
                ["terraform", "validate"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=60,
            )

            self.project_logger.debug(f"terraform validate output:\n{result.stdout}")

            if result.returncode != 0:
                error_output = result.stderr or result.stdout
                self.project_logger.error(f"terraform validate failed:\n{error_output}")
                return False, error_output

            logger.info("terraform validate completed successfully")
            return True, result.stdout

        except subprocess.TimeoutExpired:
            error_msg = "terraform validate timed out after 60 seconds"
            logger.error(error_msg)
            self.project_logger.error(error_msg)
            return False, error_msg

        except Exception as e:
            error_msg = f"Unexpected error during terraform validate: {e}"
            logger.error(error_msg)
            self.project_logger.error(error_msg)
            return False, str(e)

    def validate_with_retry(
        self, original_request: str, region: str = "eastus"
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate Terraform configuration with auto-healing retry logic.

        If validation fails, attempts to fix errors using Claude up to MAX_RETRIES times.

        Args:
            original_request: Original user request (for context when fixing)
            region: Azure region

        Returns:
            Tuple of (success, error_message)
        """
        # Try init and validation with retries
        for attempt in range(self.MAX_RETRIES):
            # Run terraform init
            init_success, init_output = self.terraform_init()
            if not init_success:
                # Init failed - try to fix if not last attempt
                if attempt < self.MAX_RETRIES - 1:
                    if self.generator is None:
                        return False, f"Terraform init failed:\n{init_output}"

                    logger.warning(
                        f"Init failed. Attempting to auto-fix (attempt {attempt + 1}/{self.MAX_RETRIES})..."
                    )

                    try:
                        current_files = self.generator.read_current_files()
                        result = self.generator.regenerate_with_fixes(
                            original_request, current_files, init_output, region
                        )
                        self.generator.write_files(result["files"])
                        logger.info("Applied fixes, retrying init...")
                        continue
                    except Exception as e:
                        logger.error(f"Failed to auto-fix errors: {e}")
                        return False, f"Auto-fix failed: {e}\n\nOriginal errors:\n{init_output}"
                else:
                    return False, f"Terraform init failed:\n{init_output}"

        # Try validation with retries
        for attempt in range(self.MAX_RETRIES):
            logger.info(f"Validation attempt {attempt + 1}/{self.MAX_RETRIES}")

            validate_success, validate_output = self.terraform_validate()

            if validate_success:
                logger.info("Terraform validation passed!")
                return True, None

            # Validation failed
            if attempt < self.MAX_RETRIES - 1:  # Not the last attempt
                if self.generator is None:
                    logger.error("Validation failed and no generator available for auto-healing")
                    return False, validate_output

                logger.warning(
                    f"Validation failed. Attempting to auto-fix (attempt {attempt + 1}/{self.MAX_RETRIES})..."
                )

                try:
                    # Read current files
                    current_files = self.generator.read_current_files()

                    # Ask Claude to fix the errors
                    result = self.generator.regenerate_with_fixes(
                        original_request, current_files, validate_output, region
                    )

                    # Write fixed files
                    self.generator.write_files(result["files"])

                    logger.info("Applied fixes, retrying validation...")

                except Exception as e:
                    logger.error(f"Failed to auto-fix errors: {e}")
                    return False, f"Auto-fix failed: {e}\n\nOriginal errors:\n{validate_output}"

            else:
                # Last attempt failed
                logger.error(f"Validation failed after {self.MAX_RETRIES} attempts")
                return False, validate_output

        return False, "Validation failed after maximum retries"
