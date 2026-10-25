"""Main CLI application for AutoCloud."""

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm
from rich import box

from autocloud.utils.config import get_config
from autocloud.utils.logger import get_logger
from autocloud.utils.helpers import (
    generate_project_id,
    save_project_metadata,
    load_project_metadata,
    get_all_projects,
    find_project_by_id,
    format_cost,
    check_terraform_installed,
    check_azure_cli_installed,
    get_azure_account_info,
    find_ssh_public_key,
    get_ssh_key_instructions,
)
from autocloud.core.generator import TerraformGenerator
from autocloud.core.validator import TerraformValidator
from autocloud.core.deployer import TerraformDeployer


app = typer.Typer(
    name="autocloud",
    help="AI-powered CLI tool for cloud infrastructure deployment",
    add_completion=False,
)
console = Console()
logger = get_logger()


def check_prerequisites() -> bool:
    """Check if required tools are installed."""
    all_ok = True

    # Check Terraform
    if not check_terraform_installed():
        console.print("[red]✗[/red] Terraform is not installed")
        console.print("  Install from: https://www.terraform.io/downloads")
        all_ok = False
    else:
        console.print("[green]✓[/green] Terraform is installed")

    # Check Azure CLI
    if not check_azure_cli_installed():
        console.print("[red]✗[/red] Azure CLI is not installed")
        console.print("  Install from: https://docs.microsoft.com/cli/azure/install-azure-cli")
        all_ok = False
    else:
        console.print("[green]✓[/green] Azure CLI is installed")

        # Check Azure login
        account_info = get_azure_account_info()
        if not account_info:
            console.print("[yellow]⚠[/yellow] Not logged into Azure")
            console.print("  Please run: [bold]az login[/bold]")
            all_ok = False
        else:
            console.print(f"[green]✓[/green] Logged into Azure ({account_info.get('name', 'Unknown')})")

    return all_ok


@app.command()
def deploy(
    request: str = typer.Argument(..., help="Natural language infrastructure request"),
    region: Optional[str] = typer.Option(None, "--region", "-r", help="Azure region"),
    auto_approve: bool = typer.Option(False, "--auto-approve", "-y", help="Skip approval prompt"),
    ssh_key_path: Optional[str] = typer.Option(None, "--ssh-key-path", help="Path to SSH public key for Linux VMs"),
):
    """Deploy infrastructure from natural language request."""
    console.print(Panel.fit(
        "[bold blue]AutoCloud Deployment[/bold blue]",
        border_style="blue"
    ))

    # Check prerequisites
    console.print("\n[bold]Checking prerequisites...[/bold]")
    if not check_prerequisites():
        console.print("\n[red]✗[/red] Prerequisites not met. Please install required tools.")
        raise typer.Exit(1)

    # Load configuration
    config = get_config()

    # Get API key
    try:
        api_key = config.get_api_key()
    except ValueError as e:
        console.print(f"\n[red]✗[/red] {e}")
        raise typer.Exit(1)

    # Use default region if not specified
    if not region:
        region = config.config.default_region

    # Generate project ID and create directory
    project_id = generate_project_id()
    project_dir = config.projects_dir / project_id

    console.print(f"\n[bold]Project ID:[/bold] {project_id}")
    console.print(f"[bold]Region:[/bold] {region}")
    console.print(f"[bold]Request:[/bold] {request}\n")

    try:
        # Step 1: Generate Terraform configuration
        console.print("[bold blue]1. Generating Terraform configuration...[/bold blue]")
        generator = TerraformGenerator(project_dir, api_key, ssh_public_key=None)
        result = generator.generate(request, region)

        # Write files
        generator.write_files(result["files"])
        console.print(f"[green]✓[/green] Generated {len(result['files'])} Terraform files")

        # Step 2: Validate with auto-healing
        console.print("\n[bold blue]2. Validating Terraform configuration...[/bold blue]")
        validator = TerraformValidator(project_dir, generator)
        valid, error = validator.validate_with_retry(request, region)

        if not valid:
            console.print(f"[red]✗[/red] Validation failed:\n{error}")
            raise typer.Exit(1)

        console.print("[green]✓[/green] Terraform configuration is valid")

        # Step 3: Plan deployment
        console.print("\n[bold blue]3. Planning deployment...[/bold blue]")
        deployer = TerraformDeployer(project_dir)
        plan_success, plan_output, resources = deployer.terraform_plan()

        if not plan_success:
            console.print(f"[red]✗[/red] Planning failed:\n{plan_output}")
            raise typer.Exit(1)

        console.print(f"[green]✓[/green] Plan created ({len(resources)} resources)")

        # Step 4: Show summary and get approval
        console.print("\n[bold]Deployment Summary:[/bold]")

        # Resources table
        if resources:
            console.print("\n[bold]Resources to create:[/bold]")
            for resource in resources[:10]:  # Show first 10
                console.print(f"  • {resource}")
            if len(resources) > 10:
                console.print(f"  ... and {len(resources) - 10} more")

        # Cost estimate
        cost_estimate = result.get("cost_estimate", {})
        if cost_estimate:
            console.print(f"\n[bold]Estimated monthly cost:[/bold] {format_cost(cost_estimate.get('monthly_total', 0), cost_estimate.get('currency', 'USD'))}")

            breakdown = cost_estimate.get("breakdown", [])
            if breakdown:
                console.print("\n[bold]Cost breakdown:[/bold]")
                for item in breakdown:
                    resource_name = item.get("resource", "Unknown")
                    cost = format_cost(item.get("monthly_cost", 0), cost_estimate.get("currency", "USD"))
                    console.print(f"  • {resource_name}: {cost}/month")

            if notes := cost_estimate.get("notes"):
                console.print(f"\n[dim]{notes}[/dim]")

        # Get approval
        if not auto_approve:
            console.print()
            if not Confirm.ask("[bold yellow]Deploy?[/bold yellow]", default=False):
                console.print("\n[yellow]Deployment cancelled[/yellow]")
                raise typer.Exit(0)

        # Step 5: Apply
        console.print("\n[bold blue]4. Deploying infrastructure...[/bold blue]")
        console.print("[dim]This may take several minutes...[/dim]\n")

        apply_success, apply_output = deployer.terraform_apply(auto_approve=True)

        if not apply_success:
            console.print(f"[red]✗[/red] Deployment failed:\n{apply_output}")

            # CRITICAL FIX: Automatic cleanup of partial deployment
            # If deployment fails (e.g., Azure capacity), some resources may have been created
            # We automatically run terraform destroy to clean them up
            console.print("\n[yellow]⚠[/yellow] Attempting automatic cleanup of partial deployment...")

            try:
                destroy_success, destroy_output = deployer.terraform_destroy(auto_approve=True)

                if destroy_success:
                    console.print("[green]✓[/green] Cleanup successful - all resources removed")
                    logger.info("Automatic cleanup after deployment failure: success")
                else:
                    console.print("[yellow]⚠[/yellow] Automatic cleanup failed")
                    console.print("[dim]Some resources may remain in Azure. Clean up manually:[/dim]")
                    console.print(f"[dim]  az group delete --name <resource-group> --yes[/dim]")
                    logger.warning(f"Automatic cleanup failed:\n{destroy_output}")

            except Exception as cleanup_error:
                console.print(f"[yellow]⚠[/yellow] Cleanup error: {cleanup_error}")
                console.print("[dim]You may need to manually delete resources from Azure portal[/dim]")
                logger.error(f"Cleanup exception: {cleanup_error}")

            # Save metadata with failed status
            metadata = {
                "id": project_id,
                "created_at": datetime.now().isoformat(),
                "request": request,
                "cloud": "azure",
                "region": region,
                "status": "failed",
                "resources": resources,
                "cost_estimate": cost_estimate,
            }
            save_project_metadata(project_dir, metadata)

            raise typer.Exit(1)

        console.print("[green]✓[/green] Infrastructure deployed successfully!")

        # Get outputs
        outputs = deployer.get_outputs()

        # Save metadata
        metadata = {
            "id": project_id,
            "created_at": datetime.now().isoformat(),
            "request": request,
            "cloud": "azure",
            "region": region,
            "status": "deployed",
            "resources": resources,
            "cost_estimate": cost_estimate,
            "outputs": outputs,
        }
        save_project_metadata(project_dir, metadata)

        # Show outputs
        if outputs:
            console.print("\n[bold]Outputs:[/bold]")
            for key, value in outputs.items():
                console.print(f"  • {key}: {value}")

        console.print(f"\n[green]✓[/green] Project saved: {project_id}")
        console.print(f"\n[bold]Next steps:[/bold]")
        console.print(f"  • View details: [bold]autocloud show {project_id}[/bold]")
        console.print(f"  • Destroy: [bold]autocloud destroy {project_id}[/bold]")

    except KeyboardInterrupt:
        console.print("\n\n[yellow]Deployment cancelled by user[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"\n[red]✗[/red] Unexpected error: {e}")
        logger.exception("Deployment failed with unexpected error")
        raise typer.Exit(1)


@app.command()
def list():
    """List all projects."""
    config = get_config()
    projects = get_all_projects(config.projects_dir)

    if not projects:
        console.print("[yellow]No projects found[/yellow]")
        console.print("\nCreate your first project:")
        console.print('  [bold]autocloud deploy "create 2 Ubuntu VMs"[/bold]')
        return

    console.print(f"\n[bold]AutoCloud Projects[/bold] ({len(projects)} total)\n")

    table = Table(box=box.ROUNDED)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Created", style="dim")
    table.add_column("Status", no_wrap=True)
    table.add_column("Region", style="blue")
    table.add_column("Resources", justify="right")
    table.add_column("Monthly Cost", justify="right")
    table.add_column("Request", max_width=40)

    for project in projects:
        project_id = project.get("id", "unknown")
        created_at = project.get("created_at", "")
        status = project.get("status", "unknown")
        region = project.get("region", "")
        resources = len(project.get("resources", []))
        cost_estimate = project.get("cost_estimate", {})
        monthly_cost = format_cost(
            cost_estimate.get("monthly_total", 0),
            cost_estimate.get("currency", "USD")
        )
        request = project.get("request", "")

        # Format status with color
        status_formatted = {
            "deployed": "[green]deployed[/green]",
            "failed": "[red]failed[/red]",
            "destroyed": "[dim]destroyed[/dim]",
        }.get(status, status)

        # Format created date
        try:
            dt = datetime.fromisoformat(created_at)
            created_str = dt.strftime("%Y-%m-%d %H:%M")
        except:
            created_str = created_at

        table.add_row(
            project_id,
            created_str,
            status_formatted,
            region,
            str(resources),
            monthly_cost,
            request[:40] + "..." if len(request) > 40 else request,
        )

    console.print(table)
    console.print()


@app.command()
def show(project_id: str = typer.Argument(..., help="Project ID")):
    """Show detailed information about a project."""
    config = get_config()
    project_dir = find_project_by_id(config.projects_dir, project_id)

    if not project_dir:
        console.print(f"[red]✗[/red] Project not found: {project_id}")
        raise typer.Exit(1)

    metadata = load_project_metadata(project_dir)

    if not metadata:
        console.print(f"[red]✗[/red] Project metadata not found")
        raise typer.Exit(1)

    # Display project details
    console.print(f"\n[bold blue]Project: {project_id}[/bold blue]\n")

    # Basic info
    console.print(f"[bold]Status:[/bold] {metadata.get('status', 'unknown')}")
    console.print(f"[bold]Created:[/bold] {metadata.get('created_at', 'unknown')}")
    console.print(f"[bold]Cloud:[/bold] {metadata.get('cloud', 'unknown')}")
    console.print(f"[bold]Region:[/bold] {metadata.get('region', 'unknown')}")
    console.print(f"[bold]Request:[/bold] {metadata.get('request', 'unknown')}")

    # Resources
    resources = metadata.get("resources", [])
    if resources:
        console.print(f"\n[bold]Resources ({len(resources)}):[/bold]")
        for resource in resources:
            console.print(f"  • {resource}")

    # Cost estimate
    cost_estimate = metadata.get("cost_estimate", {})
    if cost_estimate:
        monthly_total = format_cost(
            cost_estimate.get("monthly_total", 0),
            cost_estimate.get("currency", "USD")
        )
        console.print(f"\n[bold]Estimated monthly cost:[/bold] {monthly_total}")

        breakdown = cost_estimate.get("breakdown", [])
        if breakdown:
            for item in breakdown:
                resource_name = item.get("resource", "Unknown")
                cost = format_cost(
                    item.get("monthly_cost", 0),
                    cost_estimate.get("currency", "USD")
                )
                console.print(f"  • {resource_name}: {cost}/month")

    # Outputs
    outputs = metadata.get("outputs", {})
    if outputs:
        console.print(f"\n[bold]Outputs:[/bold]")
        for key, value in outputs.items():
            console.print(f"  • {key}: {value}")

    console.print(f"\n[bold]Project directory:[/bold] {project_dir}")
    console.print()


@app.command()
def destroy(
    project_id: str = typer.Argument(..., help="Project ID"),
    auto_approve: bool = typer.Option(False, "--auto-approve", "-y", help="Skip confirmation"),
):
    """Destroy infrastructure for a project."""
    config = get_config()
    project_dir = find_project_by_id(config.projects_dir, project_id)

    if not project_dir:
        console.print(f"[red]✗[/red] Project not found: {project_id}")
        raise typer.Exit(1)

    metadata = load_project_metadata(project_dir)

    if not metadata:
        console.print(f"[red]✗[/red] Project metadata not found")
        raise typer.Exit(1)

    if metadata.get("status") == "destroyed":
        console.print(f"[yellow]⚠[/yellow] Project already destroyed")
        return

    # Show warning
    console.print(f"\n[bold red]Warning: This will destroy all infrastructure for project {project_id}[/bold red]\n")

    resources = metadata.get("resources", [])
    if resources:
        console.print(f"[bold]Resources to destroy ({len(resources)}):[/bold]")
        for resource in resources[:10]:
            console.print(f"  • {resource}")
        if len(resources) > 10:
            console.print(f"  ... and {len(resources) - 10} more")
        console.print()

    # Get confirmation
    if not auto_approve:
        if not Confirm.ask("[bold red]Are you sure you want to destroy this infrastructure?[/bold red]", default=False):
            console.print("\n[yellow]Destruction cancelled[/yellow]")
            return

    # Destroy
    console.print("\n[bold red]Destroying infrastructure...[/bold red]")
    console.print("[dim]This may take several minutes...[/dim]\n")

    deployer = TerraformDeployer(project_dir)
    success, output = deployer.terraform_destroy(auto_approve=True)

    if not success:
        console.print(f"[red]✗[/red] Destruction failed:\n{output}")
        raise typer.Exit(1)

    # Update metadata
    metadata["status"] = "destroyed"
    metadata["destroyed_at"] = datetime.now().isoformat()
    save_project_metadata(project_dir, metadata)

    console.print(f"[green]✓[/green] Infrastructure destroyed successfully")
    console.print(f"\nProject files are still available at: {project_dir}")


@app.command()
def config(
    action: str = typer.Argument(..., help="Action: 'set' or 'get'"),
    key: Optional[str] = typer.Argument(None, help="Configuration key"),
    value: Optional[str] = typer.Argument(None, help="Configuration value (for 'set')"),
):
    """Manage AutoCloud configuration."""
    cfg = get_config()

    if action == "set":
        if not key or not value:
            console.print("[red]✗[/red] Both key and value are required for 'set'")
            raise typer.Exit(1)

        try:
            cfg.set_value(key, value)
            console.print(f"[green]✓[/green] Set {key} = {value}")
        except ValueError as e:
            console.print(f"[red]✗[/red] {e}")
            raise typer.Exit(1)

    elif action == "get":
        if not key:
            # Show all config
            console.print("\n[bold]AutoCloud Configuration:[/bold]\n")
            for k, v in cfg.config.model_dump().items():
                # Hide API key
                if "key" in k.lower() and v:
                    v = "***" + v[-4:] if len(v) > 4 else "***"
                console.print(f"  {k}: {v}")
            console.print()
        else:
            try:
                value = cfg.get_value(key)
                console.print(f"{key}: {value}")
            except ValueError as e:
                console.print(f"[red]✗[/red] {e}")
                raise typer.Exit(1)

    else:
        console.print(f"[red]✗[/red] Unknown action: {action}")
        console.print("Use 'set' or 'get'")
        raise typer.Exit(1)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-v", help="Show version"),
):
    """AutoCloud - AI-powered cloud infrastructure deployment."""
    if version:
        from autocloud import __version__
        console.print(f"AutoCloud v{__version__}")
        raise typer.Exit()

    if ctx.invoked_subcommand is None:
        console.print("[bold blue]AutoCloud[/bold blue] - AI-powered cloud infrastructure deployment\n")
        console.print("Usage: [bold]autocloud [COMMAND][/bold]\n")
        console.print("Commands:")
        console.print("  [bold cyan]deploy[/bold cyan]   Deploy infrastructure from natural language")
        console.print("  [bold cyan]list[/bold cyan]     List all projects")
        console.print("  [bold cyan]show[/bold cyan]     Show project details")
        console.print("  [bold cyan]destroy[/bold cyan]  Destroy infrastructure")
        console.print("  [bold cyan]config[/bold cyan]   Manage configuration")
        console.print("\nExamples:")
        console.print('  autocloud deploy "create 2 Ubuntu VMs with load balancer"')
        console.print("  autocloud list")
        console.print("  autocloud show proj-20250109-abc123")
        console.print("\nFor more help: [bold]autocloud [COMMAND] --help[/bold]")


if __name__ == "__main__":
    app()
