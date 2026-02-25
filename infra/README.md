# Flatris Infrastructure on AWS

Pulumi infrastructure to deploy Flatris (multiplayer Tetris game) on AWS free tier.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         AWS VPC (10.0.0.0/16)                    │
│                         ap-southeast-1 region                   │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              Public Subnet (10.0.1.0/24)                  │  │
│  │                  ap-southeast-1a                           │  │
│  │                                                           │  │
│  │  ┌─────────────────────┐      ┌─────────────────────┐    │  │
│  │  │   Flatris App       │      │  GitHub Runner       │    │  │
│  │  │   EC2 (t2.micro)    │◄─────┤  EC2 (t2.micro)     │    │  │
│  │  │                     │ SSH  │  (Bastion + Runner)  │    │  │
│  │  │  Ports:             │      │                     │    │  │
│  │  │  - 80 (HTTP)        │      │  Ports:             │    │  │
│  │  │  - 443 (HTTPS)      │      │  - 22 (SSH)         │    │  │
│  │  │  - 3000 (WebSocket) │      │  - Outbound only    │    │  │
│  │  │  - 22 (SSH from     │      │                     │    │  │
│  │  │    runner only)     │      │                     │    │  │
│  │  └─────────────────────┘      └─────────────────────┘    │  │
│  │                                                           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                  │
│                        ┌──────▼──────┐                         │
│                        │ Internet    │                         │
│                        │ Gateway     │                         │
│                        └─────────────┘                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Resources Provisioned

| Resource | Type | Purpose |
|----------|------|---------|
| **VPC** | AWS VPC | Isolated network |
| **Public Subnet** | EC2 Subnet | Public-facing instances |
| **Internet Gateway** | EC2 IGW | Internet access |
| **Security Groups** | EC2 SG | Firewall rules |
| **Flatris App** | EC2 t2.micro | Game server (no direct SSH) |
| **GitHub Runner** | EC2 t2.micro | Self-hosted CI/CD + Bastion |

## Prerequisites

- AWS account with free tier
- AWS credentials configured (`aws configure --profile flatris-access`)
- Pulumi CLI installed
- Python 3.9+ with uv

## Getting Started

### 1. Install Dependencies

```bash
cd infra
uv sync
```

### 2. Configure Stack

```bash
# AWS region is set to ap-southeast-1 in Pulumi.yaml

# (Optional) Custom instance type
pulumi config set instance_type t2.micro

# (Optional) Custom AMI (must be Ubuntu 22.04 in ap-southeast-1)
pulumi config set ami ami-01811d4912b4ccb26
```

### 3. Set SSH Key

Option A - Use existing public key:
```bash
export PUBLIC_KEY="$(cat ~/.ssh/id_rsa.pub)"
pulumi up
```

Option B - Let Pulumi generate key pair:
```bash
pulumi up
# Save the private key from outputs
```

### 4. Deploy

```bash
pulumi up
```

### 5. Get Outputs

```bash
# Get Flatris URL
pulumi stack output flatris_url

# Get SSH commands
pulumi stack output ssh_to_flatris
pulumi stack output ssh_to_runner
```

## Configuration

| Key | Default | Description |
|-----|---------|-------------|
| `aws:region` | `ap-southeast-1` | AWS region |
| `instance_type` | `t2.micro` | EC2 instance type |
| `ami` | Ubuntu 22.04 | AMI ID (ap-southeast-1) |
| `key_name` | `flatris-keypair` | SSH key name |

## Outputs

| Output | Description |
|--------|-------------|
| `flatris_app_public_ip` | App instance public IP |
| `flatris_url` | Access URL for the game |
| `ssh_to_flatris` | SSH command for app instance |
| `ssh_to_runner` | SSH command for runner |

## Post-Deployment Steps

### 1. Deploy Flatris to App Instance

```bash
SSH_CMD=$(pulumi stack output ssh_to_flatris)
scp -i ~/.ssh/flatris-keypair.pem docker-compose.yml $SSH_CMD:~/flatris/
$SSH_CMD "cd ~/flatris && docker compose up -d"
```

### 2. Configure GitHub Runner

```bash
SSH_CMD=$(pulumi stack output ssh_to_runner)
$SSH_CMD

# On runner instance:
cd /home/ubuntu/actions-runner
sudo ./config.sh --url https://github.com/kaziiriad/flatris --token <TOKEN>
sudo ./svc.sh install ubuntu
sudo ./svc.sh start
```

## Destroy

```bash
pulumi destroy
```

## Free Tier Usage

| Resource | Free Tier | This Stack |
|----------|-----------|------------|
| EC2 t2.micro | 750 hrs/month | 2 instances = 1500 hrs |
| Data Transfer | 100 GB/month | ~20-50 GB/month |
| Public IPs | 750 hrs/month | 2 IPs |

⚠️ **Note**: Using 2 t2.micro instances exceeds free tier by ~750 hours/month.

## Cost Optimization

To stay within free tier, use a single instance:
```python
# Modify __main__.py to deploy only flatris_instance
# Remove runner_instance and use GitHub-hosted runners instead
```

## Troubleshooting

### Instance not accessible
- Check security group allows your IP
- Verify instance is in `running` state
- Check AWS Console for instance logs

### SSH connection refused
- Verify key pair is correctly configured
- Check security group rules
- Wait 1-2 minutes for instance to fully boot

### GitHub runner not connecting
- Verify runner token is valid
- Check runner logs: `sudo journalctl -u actions.runner.*`