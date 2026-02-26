# CI/CD Deployment Progress

## Project Overview
Deploying Flatris (multiplayer Tetris game) to AWS free tier using GitHub Actions and Pulumi.

- **Repository**: https://github.com/kaziiriad/flatris
- **Branch**: `master`
- **Tech Stack**: Next.js, Express, Socket.io, Node.js, Docker
- **Region**: ap-southeast-1 (Singapore)

---

## Deployment Architecture

```
┌──────────────────┐     ┌──────────────────────────────────────┐
│   GitHub Push    │────▶│  GitHub Actions CI/CD                │
│   to master      │     │  ┌─────────────────────────────────┐  │
└──────────────────┘     │  │ Test Job (ubuntu-latest)        │  │
                         │  │ - yarn install                  │  │
                         │  │ - yarn test (flow, lint, jest) │  │
                         │  └─────────────────────────────────┘  │
                         │                  │                    │
                         │                  ▼                    │
                         │  ┌─────────────────────────────────┐  │
                         │  │ Deploy Job (self-hosted)        │  │
                         │  │ - Runs on Runner EC2            │  │
                         │  │ - SSH via bastion to App EC2    │  │
                         │  │ - docker-compose up -d --build  │  │
                         │  └─────────────────────────────────┘  │
                         └──────────────────────────────────────┘
                                        │
                                        ▼
                         ┌──────────────────────────────────────┐
                         │  AWS EC2 (ap-southeast-1)           │
                         │  ┌────────────┐    ┌──────────────┐  │
                         │  │ Runner EC2 │───▶│  App EC2     │  │
                         │  │ (Bastion)  │SSH │  (Private)   │  │
                         │  │ t3.micro   │    │  t3.micro    │  │
                         │  └────────────┘    │  Port 3000   │  │
                         │                    └──────────────┘  │
                         └──────────────────────────────────────┘
                                        │
                                        ▼
                              Playable URL (http://<app-ip>:3000)
```

---

## Implementation Progress

### Repository Setup
- Forked repository from `likeabosslearning/flatris` → `kaziiriad/flatris`
- Configured GitHub CLI for repository management
- Created and merged multiple feature branches during development

### Docker Containerization
- Created `Dockerfile` with multi-stage build:
  - Builder stage: Node.js 16 Alpine, install dependencies, build Next.js
  - Production stage: Copy built artifacts and node_modules
  - Fixed Yarn version (v1.22.19 instead of v4 to avoid fetch errors)
  - Fixed `.next` path (located inside `web/` directory)
- Created `docker-compose.yml` with `without-nginx` profile
- Created `.dockerignore` to exclude unnecessary files
- Tested container locally with `docker-compose up`

### AWS Infrastructure (Pulumi)
- Created Pulumi project using Python runtime with uv
- Configured VPC with public subnet
- Configured Internet Gateway for internet access
- Created Security Groups:
  - **Runner SG**: Port 22 (SSH) from 0.0.0.0/0 (bastion access)
  - **App SG**: Ports 80, 443, 3000 from 0.0.0.0/0 (HTTP/HTTPS/App)
  - **App SG**: Port 22 from Runner SG only (bastion pattern)
- Created EC2 Key Pair `flatris-keypair` via AWS CLI
- Launched EC2 Instances:
  - **Runner EC2** (t3.micro): Public IP, acts as bastion host
  - **App EC2** (t3.micro): Private IP, runs Flatris application
- Configured IAM policies for Pulumi state backend (S3, DynamoDB)
- Set up user data scripts for Docker installation

### GitHub Actions Workflows
- **`.github/workflows/deploy-infra.yml`**
  - Triggered by changes to `infra/**`
  - Runs on GitHub-hosted `ubuntu-latest`
  - Installs Pulumi and uv
  - Runs `pulumi up --yes`
  - Exports: runner_public_ip, flatris_app_public_ip, flatris_url

- **`.github/workflows/configure-runner.yml`**
  - Triggered manually via workflow_dispatch
  - Runs on GitHub-hosted `ubuntu-latest`
  - Downloads GitHub Actions Runner (v2.331.0)
  - Configures runner with `--unattended --replace` flags
  - Installs as systemd service via `svc.sh`
  - Uses environment variable for RUNNER_TOKEN to avoid heredoc issues

- **`.github/workflows/deploy-flatris.yml`**
  - Triggered by changes to app code files
  - **Test job** (ubuntu-latest):
    - Installs Node.js 16 and Yarn 1.22.19
    - Installs dependencies with retry logic
    - Runs `yarn test` (flow type check, lint, jest)
  - **Deploy job** (self-hosted):
    - Configures SSH key with proper permissions
    - Sets up SSH config with ProxyJump for bastion access
    - Copies files via rsync to app server
    - Runs docker-compose directly on app server
    - Performs health check on port 3000

### GitHub Secrets Configuration
- `AWS_ACCESS_KEY_ID` - AWS credentials for Pulumi
- `AWS_SECRET_ACCESS_KEY` - AWS secret access key
- `PULUMI_ACCESS_TOKEN` - Pulumi backend authentication
- `SSH_PRIVATE_KEY` - EC2 key pair for SSH access (~/.ssh/flatris-keypair.pem)
- `RUNNER_TOKEN` - GitHub Actions runner registration (expires in 1-2 hours)

### Deployment Automation
- Automated testing on every push (flow type checking, ESLint, Jest tests)
- Automated infrastructure deployment via Pulumi on infra changes
- Self-hosted runner configuration workflow for initial setup
- Automated application deployment via SSH + docker-compose
- Health check verification after deployment

### Testing Status
- Unit tests pass (timeout-bumper.test.js, cosmos.test.js)
- Container builds and runs locally
- Infrastructure deploys successfully via Pulumi
- GitHub Actions runner configures and connects
- Deployment pipeline executes end-to-end

---

## GitHub Actions Workflow Files

| File | Purpose | Runner | Trigger |
|------|---------|--------|---------|
| `deploy-infra.yml` | Deploy AWS infrastructure | ubuntu-latest | Changes in `infra/**` |
| `configure-runner.yml` | Set up self-hosted runner | ubuntu-latest | Manual (workflow_dispatch) |
| `deploy-flatris.yml` | Deploy Flatris application | self-hosted | Changes in app code files |

---

## Infrastructure Components

### EC2 Instances

| Instance | Type | Purpose | IP Type | Access |
|----------|------|---------|---------|--------|
| flatris-runner | t3.micro | GitHub Actions bastion | Public | SSH from anywhere (0.0.0.0/0:22) |
| flatris-app | t3.micro | Flatris application | Private | SSH from runner only, HTTP/HTTPS/App from anywhere |

### Security Groups

| Security Group | Rules | Purpose |
|----------------|-------|---------|
| runner-sg | Port 22: 0.0.0.0/0 | Allow SSH to bastion from anywhere |
| app-sg | Ports 80, 443, 3000: 0.0.0.0/0 | Allow public HTTP/HTTPS/App access |
| app-sg | Port 22: runner-sg | Allow SSH from bastion only (private access) |

---

## Deployment Flow

1. **Developer pushes code to `master` branch**
2. **GitHub Actions evaluates triggers**:
   - If `infra/**` changed → Run `deploy-infra.yml`
   - If app code changed → Run `deploy-flatris.yml`
3. **Test job** runs on GitHub-hosted runner (fast, free)
   - Installs dependencies
   - Runs tests (flow, lint, jest)
   - If tests fail, pipeline stops
4. **If tests pass**, deploy job runs on self-hosted runner
   - Sets up SSH key with proper permissions
   - Configures SSH with ProxyJump (bastion pattern)
   - Connects to app EC2 through runner EC2
   - Copies files via rsync
   - Runs `docker-compose down` to stop old containers
   - Runs `docker-compose up -d --build` to build and start
   - Waits for health check (curl http://localhost:3000/favicon.ico)
5. **Application is live** at `http://<app-public-ip>:3000`

---

## Key Technical Decisions

### Why Self-Hosted Runner for Deployment?
- **Security**: App EC2 is in private subnet, only accessible via bastion
- **Cost**: Tests run on free GitHub-hosted runners
- **Control**: Full control over deployment environment with Docker

### Why Direct SSH + Docker Compose instead of Ansible?
- **Simplicity**: Fewer dependencies and moving parts
- **Debugging**: Easier to troubleshoot SSH issues
- **Speed**: No need to install Ansible collections on every run

### Why Pulumi over Terraform?
- **Choice**: User preference for Python over HCL
- **State Management**: Built-in state backend
- **AWS Integration**: First-class AWS provider support

### Why Bastion Pattern?
- **Security**: App instance SSH access restricted to runner only
- **Compliance**: Private subnet for application tier
- **Flexibility**: Can add more instances behind the bastion

---

## Commands Reference

### Local Testing
```bash
# Build and run locally
docker-compose --profile without-nginx up -d --build

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Run tests
yarn install
yarn test
```

### Pulumi Infrastructure
```bash
cd infra

# Install dependencies using uv
uv sync

# Preview infrastructure changes
pulumi preview

# Deploy infrastructure
pulumi up

# Get outputs
pulumi stack output runner_public_ip
pulumi stack output flatris_app_public_ip
pulumi stack output flatris_app_private_ip
pulumi stack output flatris_url

# Select stack
pulumi stack select flatris-dev
```

### Manual Deployment (for debugging)
```bash
# SSH into app instance via bastion
ssh -i ~/.ssh/flatris-keypair.pem ubuntu@<runner-public-ip>
ssh ubuntu@<app-private-ip>

# On app instance:
cd /home/ubuntu/flatris-repo
docker-compose -f docker-compose.yml --profile without-nginx up -d --build

# View logs
docker-compose -f docker-compose.yml --profile without-nginx logs -f

# Check containers
docker ps
```

---

## Environment Variables

### Required GitHub Secrets
- `AWS_ACCESS_KEY_ID` - AWS access key for Pulumi
- `AWS_SECRET_ACCESS_KEY` - AWS secret key
- `PULUMI_ACCESS_TOKEN` - Pulumi authentication token
- `SSH_PRIVATE_KEY` - EC2 key pair private key contents
- `RUNNER_TOKEN` - GitHub Actions runner registration (get from Settings → Actions → Runners)

### Application Environment (Optional)
- `NODE_ENV=production`
- `PORT=3000`

---

## Troubleshooting

### Runner appears offline in GitHub
- **Cause**: Token expires after 1-2 hours, or runner service not running
- **Fix**:
  - Get new token from https://github.com/kaziiriad/flatris/settings/actions/runners
  - Update `RUNNER_TOKEN` secret
  - Re-run `configure-runner.yml` workflow

### SSH permission denied
- **Cause**: Key file has wrong permissions or corrupted
- **Fix**:
  - Check permissions: `ls -la ~/.ssh/flatris-keypair.pem` (should be 400)
  - Remove old key: `rm -f ~/.ssh/flatris-keypair.pem`
  - Re-run deployment

### Deployment fails - "App instance not ready"
- **Cause**: App EC2 still booting or security group misconfigured
- **Fix**:
  - Check if instance is running: `pulumi stack output flatris_app_public_ip`
  - Verify security group allows SSH from runner
  - Check user data script completed successfully

### Container won't start
- **Cause**: Build error or port conflict
- **Fix**:
  - SSH into app instance: `ssh flatris-app`
  - Check logs: `cd /home/ubuntu/flatris-repo && docker-compose logs`
  - Rebuild: `docker-compose up -d --build`

### Yarn install fails with "fetch is not defined"
- **Cause**: Yarn v4 compatibility issue
- **Fix**: Already fixed in Dockerfile using Yarn v1.22.19

---

## Free Tier Considerations

- **t3.micro** instances in `ap-southeast-1` are eligible for free tier
- Free tier provides **750 hours/month** of EC2 compute
- **Current usage**: 2 instances × ~730 hours/month ≈ **1460 hours**
- **Cost implication**: May exceed free tier if both run 24/7
- **Savings tip**: Stop instances when not in use (`pulumi destroy` or manual stop)

---

## Next Steps

- Test multiplayer WebSocket functionality with multiple users
- Perform load testing
- Set up custom domain name
- Configure SSL/TLS with Let's Encrypt (optional)
- Add monitoring/alerting (CloudWatch, etc.)

---

*Last Updated: 2025-02-26*