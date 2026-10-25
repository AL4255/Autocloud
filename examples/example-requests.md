# Example AutoCloud Requests

This file contains example natural language requests you can use with AutoCloud.

## Virtual Machines

```bash
# Basic VMs
autocloud deploy "create 2 Ubuntu 22.04 VMs"
autocloud deploy "create 3 Windows Server 2022 VMs with 8GB RAM"
autocloud deploy "create a Linux VM with 4 cores and 16GB memory"

# VMs with networking
autocloud deploy "create 2 VMs with a load balancer"
autocloud deploy "create web server VMs with public IPs"
autocloud deploy "create 3 app servers in a private subnet"
```

## Databases

```bash
# PostgreSQL
autocloud deploy "create PostgreSQL database"
autocloud deploy "create PostgreSQL flexible server with 100GB storage"

# MySQL
autocloud deploy "create MySQL database"

# SQL Server
autocloud deploy "create Azure SQL Database"
```

## Storage

```bash
# Blob Storage
autocloud deploy "create blob storage account"
autocloud deploy "create storage account with private endpoint"
autocloud deploy "create storage with lifecycle management"

# File Shares
autocloud deploy "create Azure Files share with 100GB capacity"
```

## Networking

```bash
# Virtual Networks
autocloud deploy "create VNet with 3 subnets"
autocloud deploy "create virtual network with public and private subnets"

# Security
autocloud deploy "create network security group with SSH and HTTP rules"
autocloud deploy "create VNet with NSG allowing ports 80, 443, and 22"

# Load Balancers
autocloud deploy "create public load balancer for web traffic"
autocloud deploy "create internal load balancer"
```

## Complete Stacks

```bash
# Web Application
autocloud deploy "create web app stack with 2 VMs, load balancer, and PostgreSQL database"

# Three-tier architecture
autocloud deploy "create 3-tier app with web VMs, app VMs, database, and load balancers"

# Development environment
autocloud deploy "create dev environment with VM, database, and storage"

# Microservices
autocloud deploy "create 3 VMs for microservices with shared PostgreSQL database"
```

## Kubernetes

```bash
# AKS Cluster
autocloud deploy "create AKS cluster with 3 nodes"
autocloud deploy "create Kubernetes cluster with autoscaling"
```

## Monitoring & Management

```bash
# Log Analytics
autocloud deploy "create Log Analytics workspace"

# Application Insights
autocloud deploy "create Application Insights for monitoring"
```

## Complex Examples

```bash
# E-commerce platform
autocloud deploy "create e-commerce platform with web VMs, app VMs, Redis cache, PostgreSQL database, and blob storage"

# Data processing pipeline
autocloud deploy "create data pipeline with VMs, storage account, and PostgreSQL"

# High availability setup
autocloud deploy "create HA web application with 3 VMs across availability zones, load balancer, and managed database"
```

## Tips for Better Results

1. **Be Specific**: Include details like VM size, OS, storage capacity
2. **Mention Security**: Specify public/private, encryption needs
3. **Name Resources**: Use descriptive names for your infrastructure
4. **Specify Regions**: Use `--region` flag for specific Azure regions
5. **Include Networking**: Mention subnets, NSGs, load balancers if needed

## Example with Flags

```bash
# Specify region
autocloud deploy "create 2 VMs" --region westus2

# Auto-approve (skip confirmation)
autocloud deploy "create storage account" --auto-approve

# Combined
autocloud deploy "create PostgreSQL database" --region eastus2 --auto-approve
```
