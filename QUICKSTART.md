# AutoCloud Quick Start Guide

Get AutoCloud up and running in 5 minutes!

## Prerequisites Checklist

Before starting, ensure you have:

- [ ] Python 3.10 or higher installed
- [ ] Terraform 1.6.0 or higher installed
- [ ] Azure CLI installed and configured
- [ ] Anthropic API key (from https://console.anthropic.com/)
- [ ] Active Azure subscription

## Step 1: Install Dependencies

```bash
# Navigate to AutoCloud directory
cd AutoCloud

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install AutoCloud in development mode
pip install -e .
```

## Step 2: Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env and add your Anthropic API key
# ANTHROPIC_API_KEY=sk-ant-your-key-here
```

## Step 3: Authenticate with Azure

```bash
# Login to Azure
az login

# Verify your login
az account show

# (Optional) Set default subscription if you have multiple
az account set --subscription "Your Subscription Name"
```

## Step 4: Verify Installation

```bash
# Check AutoCloud version
autocloud --version

# Run prerequisite check (this runs automatically on deploy)
autocloud deploy "test" --help
```

## Step 5: Your First Deployment

```bash
# Deploy a simple resource group and storage account
autocloud deploy "create a storage account for testing"

# The CLI will:
# 1. Check prerequisites ✓
# 2. Generate Terraform code using Claude AI
# 3. Validate the configuration
# 4. Show estimated costs
# 5. Ask for approval
# 6. Deploy to Azure
# 7. Show outputs and connection details
```

## Step 6: Manage Your Infrastructure

```bash
# List all projects
autocloud list

# Show project details (replace with your project ID)
autocloud show proj-20250109-abc123

# Destroy infrastructure when done
autocloud destroy proj-20250109-abc123
```

## Common Commands

### Deploy Infrastructure

```bash
# Basic deployment
autocloud deploy "create 2 Ubuntu VMs"

# Specify region
autocloud deploy "create PostgreSQL database" --region westus2

# Skip approval prompt
autocloud deploy "create storage account" --auto-approve
```

### View Projects

```bash
# List all projects
autocloud list

# Show specific project
autocloud show <project-id>
```

### Clean Up

```bash
# Destroy infrastructure (with confirmation)
autocloud destroy <project-id>

# Destroy without confirmation
autocloud destroy <project-id> --auto-approve
```

### Configuration

```bash
# View all config
autocloud config get

# Set API key
autocloud config set anthropic_api_key sk-ant-...

# Set default region
autocloud config set default_region westus2
```

## Example Workflows

### Web Application Stack

```bash
# Create complete web stack
autocloud deploy "create web app with 2 VMs, load balancer, and PostgreSQL database"

# Check the deployment
autocloud list

# Get connection details
autocloud show <project-id>
```

### Development Environment

```bash
# Create dev environment
autocloud deploy "create development environment with Linux VM and PostgreSQL"

# Work with your infrastructure...

# Clean up when done
autocloud destroy <project-id>
```

## Troubleshooting

### Issue: "terraform command not found"

```bash
# Install Terraform
# macOS:
brew install terraform

# Other platforms:
# Download from https://www.terraform.io/downloads
```

### Issue: "Not logged into Azure"

```bash
# Login to Azure
az login

# Verify
az account show
```

### Issue: "Anthropic API key not found"

```bash
# Set in environment
export ANTHROPIC_API_KEY=sk-ant-your-key-here

# Or set in config
autocloud config set anthropic_api_key sk-ant-your-key-here
```

### Issue: "Validation failed"

AutoCloud automatically retries validation up to 3 times. If it still fails:

1. Check logs in `~/.autocloud/projects/<project-id>/logs/`
2. Review Terraform files manually
3. Try with a more specific request

### Issue: "Permission denied" errors

Ensure your Azure account has appropriate permissions:

```bash
# Check current account
az account show

# List available subscriptions
az account list --output table

# Switch subscription if needed
az account set --subscription "Subscription Name"
```

## Next Steps

1. **Read the README**: Comprehensive documentation in [README.md](README.md)
2. **Try Examples**: See [examples/example-requests.md](examples/example-requests.md)
3. **Run Tests**: `pytest` to run the test suite
4. **Contribute**: See [CONTRIBUTING.md](CONTRIBUTING.md)

## Project Structure

```
~/.autocloud/                    # AutoCloud home directory
├── config.json                  # Configuration
└── projects/                    # All your projects
    ├── proj-20250109-abc123/   # Example project
    │   ├── main.tf             # Terraform files
    │   ├── variables.tf
    │   ├── outputs.tf
    │   ├── providers.tf
    │   ├── terraform.tfvars
    │   ├── metadata.json       # Project metadata
    │   ├── .terraform/         # Terraform state
    │   └── logs/               # Deployment logs
    └── proj-20250109-xyz789/
```

## Tips for Success

1. **Be Specific**: "create 2 Ubuntu 22.04 VMs with 4GB RAM" is better than "create VMs"
2. **Check Costs**: Review estimated costs before approving deployment
3. **Use Regions Wisely**: Specify regions closest to your users
4. **Clean Up**: Remember to destroy resources you're not using
5. **Check Logs**: Logs in project directories help debug issues

## Getting Help

- **Documentation**: Check [README.md](README.md)
- **Examples**: Browse [examples/example-requests.md](examples/example-requests.md)
- **Issues**: Report bugs at GitHub Issues
- **Logs**: Check `~/.autocloud/projects/<project-id>/logs/` for detailed logs

## Ready to Deploy!

You're all set! Try your first deployment:

```bash
autocloud deploy "create a simple web server VM with Ubuntu"
```

Happy deploying! 🚀

