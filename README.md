# AutoCloud

**AI-powered CLI tool that converts natural language into deployed cloud infrastructure.**

AutoCloud takes your natural language requests and automatically generates, validates, and deploys production-ready infrastructure on Azure using Terraform and Claude AI.

## Features
 
- **Natural Language to Infrastructure**: Describe what you need, AutoCloud handles the rest
- **Intelligent Generation**: Uses Claude AI to generate production-ready Terraform code
- **Self-Healing Validation**: Automatically fixes Terraform errors (up to 3 attempts)
- **Cost Estimation**: Get estimated monthly costs before deployment
- **Project Management**: List, view, and destroy infrastructure easily
- **Beautiful CLI**: Rich terminal output with progress indicators and colors

## Quick Start

### Prerequisites

1. **Terraform** (1.6.0+)
   - macOS: `brew install terraform`
   - Other: https://www.terraform.io/downloads

2. **Azure CLI**
   - macOS: `brew install azure-cli`
   - Other: https://docs.microsoft.com/cli/azure/install-azure-cli

3. **Python** (3.10+)

4. **Anthropic API Key**
   - Sign up at: https://console.anthropic.com/
   - Get your API key from the dashboard

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/autocloud.git
cd autocloud

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install AutoCloud in development mode
pip install -e .
```

### Configuration

1. **Set up environment variables**:

```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

2. **Login to Azure**:

```bash
az login
```

3. **Verify setup**:

```bash
autocloud --version
```

## Usage

### Deploy Infrastructure

```bash
# Basic deployment
autocloud deploy "create 2 Ubuntu VMs with a load balancer"

# Specify region
autocloud deploy "create a PostgreSQL database" --region westus2

# Auto-approve (skip confirmation)
autocloud deploy "create storage account" --auto-approve
```

### List Projects

```bash
autocloud list
```

### Show Project Details

```bash
autocloud show proj-20250109-abc123
```

### Destroy Infrastructure

```bash
# With confirmation prompt
autocloud destroy proj-20250109-abc123

# Auto-approve
autocloud destroy proj-20250109-abc123 --auto-approve
```

### Manage Configuration

```bash
# View all configuration
autocloud config get

# Get specific value
autocloud config get default_region

# Set value
autocloud config set default_region westus2
autocloud config set anthropic_api_key sk-ant-...
```

## How It Works

1. **Generate**: AutoCloud sends your request to Claude AI, which generates Terraform configuration files
2. **Validate**: Runs `terraform init` and `terraform validate`
3. **Self-Heal**: If validation fails, sends errors back to Claude to fix (up to 3 attempts)
4. **Plan**: Creates a Terraform plan showing what will be created
5. **Estimate**: Shows estimated monthly costs and resource breakdown
6. **Approve**: Asks for confirmation (unless `--auto-approve` is used)
7. **Deploy**: Runs `terraform apply` to create infrastructure
8. **Save**: Stores project metadata and outputs

## Project Structure

```
autocloud/
├── autocloud/
│   ├── cli.py              # Main CLI entry point
│   ├── core/
│   │   ├── llm.py          # Claude API integration
│   │   ├── generator.py    # Terraform generation
│   │   ├── validator.py    # Validation with retry logic
│   │   └── deployer.py     # Terraform execution
│   └── utils/
│       ├── config.py       # Configuration management
│       ├── logger.py       # Logging setup
│       └── helpers.py      # Utility functions
├── tests/                  # Test suite
├── requirements.txt        # Python dependencies
└── setup.py               # Package setup
```

## Configuration

AutoCloud stores configuration in `~/.autocloud/config.json`:

```json
{
  "cloud": "azure",
  "default_region": "eastus",
  "anthropic_api_key": "sk-ant-...",
  "terraform_version": "1.6.0",
  "auto_approve": false
}
```

### Environment Variables

- `ANTHROPIC_API_KEY` - Claude API key (required)
- `AZURE_SUBSCRIPTION_ID` - Azure subscription (optional, uses `az` CLI if not set)
- `AUTOCLOUD_HOME` - Override default `~/.autocloud/` directory
- `AZURE_DEFAULT_REGION` - Default Azure region
- `AUTOCLOUD_DEBUG` - Enable debug logging

## Project Storage

Each project is stored in `~/.autocloud/projects/proj-{YYYYMMDD}-{random}/`:

```
proj-20250109-abc123/
├── main.tf              # Resource definitions
├── variables.tf         # Variable declarations
├── outputs.tf          # Output definitions
├── providers.tf        # Provider configuration
├── terraform.tfvars    # Variable values
├── metadata.json       # Project metadata
├── .terraform/         # Terraform state
└── logs/              # Generation and deployment logs
    ├── generation_*.log
    └── deployment_*.log
```

## Examples

### Create Virtual Machines

```bash
autocloud deploy "create 3 Ubuntu 22.04 VMs with 4GB RAM in eastus"
```

### Deploy Web Application Stack

```bash
autocloud deploy "create web app stack with 2 VMs, load balancer, and PostgreSQL database"
```

### Create Storage

```bash
autocloud deploy "create blob storage account with private endpoint"
```

### Network Infrastructure

```bash
autocloud deploy "create VNet with 3 subnets and network security groups"
```

## Troubleshooting

### Terraform not found

```bash
# Install Terraform
brew install terraform  # macOS
# Or download from https://www.terraform.io/downloads
```

### Azure authentication failed

```bash
# Login to Azure
az login

# Verify account
az account show
```

### API key not found

```bash
# Set API key in environment
export ANTHROPIC_API_KEY=sk-ant-your-key-here

# Or set in config
autocloud config set anthropic_api_key sk-ant-your-key-here
```

### Validation failures

AutoCloud automatically retries validation up to 3 times. If it still fails:

1. Check the logs in `~/.autocloud/projects/{project-id}/logs/`
2. Review the Terraform files manually
3. Try a more specific request

## Security Considerations 

- API keys are never logged
- Credentials stored in `~/.autocloud/` (ensure proper file permissions)
- Uses Azure CLI credentials (follows Azure best practices)
- Terraform state stored locally (consider remote state for production)
- Network resources default to private (public IPs only when requested)

## Limitations (MVP)

- Azure only (AWS/GCP coming later)
- Local state management (remote state coming later)
- CLI only (web UI coming later)
- Single user (team features coming later)
- Basic resources (VMs, networking, storage, databases)

## Roadmap

### Phase 2
- [ ] Remote state support (Azure Blob Storage)
- [ ] AWS and GCP support
- [ ] Advanced security scanning (tfsec integration)
- [ ] Cost optimization recommendations
- [ ] Resource tagging and organization

### Phase 3
- [ ] Visual workflow builder (n8n-style)
- [ ] Team collaboration features
- [ ] Web dashboard
- [ ] CI/CD integration
- [ ] Policy as code

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details

## Support

- Issues: https://github.com/yourusername/autocloud/issues
- Documentation: https://github.com/yourusername/autocloud/wiki

## Acknowledgments

- Built with [Anthropic Claude](https://www.anthropic.com/)
- Powered by [Terraform](https://www.terraform.io/)
- CLI built with [Typer](https://typer.tiangolo.com/) and [Rich](https://rich.readthedocs.io/)

   
