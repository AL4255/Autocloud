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
