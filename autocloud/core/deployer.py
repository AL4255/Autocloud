"""Terraform deployment execution."""

import logging
import subprocess
from pathlib import Path
from typing import Tuple, List, Dict, Any

from autocloud.utils.logger import get_project_logger
from autocloud.utils.helpers import parse_terraform_resources


logger = logging.getLogger("autocloud")


class TerraformDeployer:
    """Handles Terraform plan and apply operations."""

    def __init__(self, project_dir: Path):
        """
        Initialize Terraform deployer.

        Args:
            project_dir: Directory containing Terraform files
        """
        self.project_dir = project_dir
        self.project_logger = get_project_logger(project_dir, "deployment")

    def terraform_plan(self) -> Tuple[bool, str, List[str]]:
        """
        Run terraform plan.

        Returns:
            Tuple of (success, output, resources)
        """
        logger.info("Running terraform plan...")
        self.project_logger.info("Running terraform plan")

        try:
            result = subprocess.run(
                ["terraform", "plan", "-out=tfplan"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            self.project_logger.debug(f"terraform plan output:\n{result.stdout}")

            if result.returncode != 0:
                error_output = result.stderr or result.stdout
                self.project_logger.error(f"terraform plan failed:\n{error_output}")
                return False, error_output, []

            # Parse resources from plan output
            resources = parse_terraform_resources(result.stdout)
            self.project_logger.info(f"Plan includes {len(resources)} resources")

            logger.info(f"terraform plan completed successfully ({len(resources)} resources)")
            return True, result.stdout, resources

        except subprocess.TimeoutExpired:
            error_msg = "terraform plan timed out after 5 minutes"
            logger.error(error_msg)
            self.project_logger.error(error_msg)
            return False, error_msg, []

        except Exception as e:
            error_msg = f"Unexpected error during terraform plan: {e}"
            logger.error(error_msg)
            self.project_logger.error(error_msg)
            return False, str(e), []

    def terraform_apply(self, auto_approve: bool = False) -> Tuple[bool, str]:
        """
        Run terraform apply.

        Args:
            auto_approve: If True, skip interactive approval

        Returns:
            Tuple of (success, output)
        """
        logger.info("Running terraform apply...")
        self.project_logger.info("Running terraform apply")

        cmd = ["terraform", "apply"]

        if auto_approve:
            cmd.append("-auto-approve")
            cmd.append("tfplan")
        else:
            # If we have a saved plan, use it
            plan_file = self.project_dir / "tfplan"
            if plan_file.exists():
                cmd.append("tfplan")

        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=1800,  # 30 minute timeout
            )

            self.project_logger.debug(f"terraform apply output:\n{result.stdout}")

            if result.returncode != 0:
                error_output = result.stderr or result.stdout
                self.project_logger.error(f"terraform apply failed:\n{error_output}")
                return False, error_output

            logger.info("terraform apply completed successfully")
            self.project_logger.info("Deployment completed successfully")
            return True, result.stdout

        except subprocess.TimeoutExpired:
            error_msg = "terraform apply timed out after 30 minutes"
            logger.error(error_msg)
            self.project_logger.error(error_msg)
            return False, error_msg

        except Exception as e:
            error_msg = f"Unexpected error during terraform apply: {e}"
            logger.error(error_msg)
            self.project_logger.error(error_msg)
            return False, str(e)

    def terraform_destroy(self, auto_approve: bool = False) -> Tuple[bool, str]:
        """
        Run terraform destroy to tear down infrastructure.

        Args:
            auto_approve: If True, skip interactive approval

        Returns:
            Tuple of (success, output)
        """
        logger.info("Running terraform destroy...")
        self.project_logger.info("Running terraform destroy")

        cmd = ["terraform", "destroy"]

        if auto_approve:
            cmd.append("-auto-approve")

        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=1800,  # 30 minute timeout
            )

            self.project_logger.debug(f"terraform destroy output:\n{result.stdout}")

            if result.returncode != 0:
                error_output = result.stderr or result.stdout
                self.project_logger.error(f"terraform destroy failed:\n{error_output}")
                return False, error_output

            logger.info("terraform destroy completed successfully")
            self.project_logger.info("Destruction completed successfully")
            return True, result.stdout

        except subprocess.TimeoutExpired:
            error_msg = "terraform destroy timed out after 30 minutes"
            logger.error(error_msg)
            self.project_logger.error(error_msg)
            return False, error_msg

        except Exception as e:
            error_msg = f"Unexpected error during terraform destroy: {e}"
            logger.error(error_msg)
            self.project_logger.error(error_msg)
            return False, str(e)

    def get_outputs(self) -> Dict[str, Any]:
        """
        Get Terraform outputs.

        Returns:
            Dictionary of output values
        """
        logger.info("Reading terraform outputs...")

        try:
            result = subprocess.run(
                ["terraform", "output", "-json"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                logger.warning("Failed to read terraform outputs")
                return {}

            import json

            outputs = json.loads(result.stdout)

            # Extract values from the output format
            simplified = {}
            for key, value in outputs.items():
                if isinstance(value, dict) and "value" in value:
                    simplified[key] = value["value"]
                else:
                    simplified[key] = value

            return simplified

        except Exception as e:
            logger.warning(f"Failed to read terraform outputs: {e}")
            return {}
