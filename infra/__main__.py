import pulumi
import pulumi_aws as aws
import os

# Configuration
config = pulumi.Config()
instance_type = config.get('instance_type', 't3.micro')
ami = config.get('ami', 'ami-01811d4912b4ccb26')  # Ubuntu 22.04 in ap-southeast-1
region = config.get('aws:region', 'ap-southeast-1')
key_name = config.get('key_name', 'flatris-keypair')

# Create VPC
vpc = aws.ec2.Vpc(
    'flatris-vpc',
    cidr_block='10.0.0.0/16',
    enable_dns_support=True,
    enable_dns_hostnames=True,
    tags={'Name': 'flatris-vpc'}
)

# Create public subnet
public_subnet = aws.ec2.Subnet(
    'flatris-public-subnet',
    vpc_id=vpc.id,
    cidr_block='10.0.1.0/24',
    map_public_ip_on_launch=True,
    availability_zone='ap-southeast-1a',
    tags={'Name': 'flatris-public-subnet'}
)

# Internet Gateway
internet_gateway = aws.ec2.InternetGateway(
    'flatris-internet-gateway',
    vpc_id=vpc.id,
    tags={'Name': 'flatris-internet-gateway'}
)

# Route Table
public_route_table = aws.ec2.RouteTable(
    'flatris-public-route-table',
    vpc_id=vpc.id,
    routes=[aws.ec2.RouteTableRouteArgs(
        cidr_block='0.0.0.0/0',
        gateway_id=internet_gateway.id
    )],
    tags={'Name': 'flatris-public-route-table'}
)

# Associate route table with subnet
public_route_table_association = aws.ec2.RouteTableAssociation(
    'flatris-public-route-table-association',
    subnet_id=public_subnet.id,
    route_table_id=public_route_table.id
)

# Security Group for GitHub Runner (Bastion + Runner)
runner_security_group = aws.ec2.SecurityGroup(
    'flatris-runner-security-group',
    vpc_id=vpc.id,
    ingress=[
        # SSH from anywhere (will be used as bastion)
        aws.ec2.SecurityGroupIngressArgs(
            cidr_blocks=['0.0.0.0/0'],
            from_port=22,
            to_port=22,
            protocol='tcp',
            description='SSH (Bastion)'
        ),
    ],
    egress=[
        aws.ec2.SecurityGroupEgressArgs(
            cidr_blocks=['0.0.0.0/0'],
            from_port=0,
            to_port=0,
            protocol='-1'
        )
    ],
    tags={'Name': 'flatris-runner-security-group'}
)

# Security Group for Flatris App (HTTP, HTTPS, WebSocket only)
# SSH access only from runner/bastion
app_security_group = aws.ec2.SecurityGroup(
    'flatris-app-security-group',
    vpc_id=vpc.id,
    ingress=[
        # HTTP
        aws.ec2.SecurityGroupIngressArgs(
            cidr_blocks=['0.0.0.0/0'],
            from_port=80,
            to_port=80,
            protocol='tcp',
            description='HTTP'
        ),
        # HTTPS
        aws.ec2.SecurityGroupIngressArgs(
            cidr_blocks=['0.0.0.0/0'],
            from_port=443,
            to_port=443,
            protocol='tcp',
            description='HTTPS'
        ),
        # WebSocket support (upgrades from HTTP)
        aws.ec2.SecurityGroupIngressArgs(
            cidr_blocks=['0.0.0.0/0'],
            from_port=3000,
            to_port=3000,
            protocol='tcp',
            description='Flatris App (WebSocket)'
        ),
    ],
    egress=[
        aws.ec2.SecurityGroupEgressArgs(
            cidr_blocks=['0.0.0.0/0'],
            from_port=0,
            to_port=0,
            protocol='-1'
        )
    ],
    tags={'Name': 'flatris-app-security-group'}
)

# SSH rule from runner to app (after runner SG is created)
app_ssh_from_runner = aws.ec2.SecurityGroupRule(
    'app-ssh-from-runner',
    type='ingress',
    from_port=22,
    to_port=22,
    protocol='tcp',
    source_security_group_id=runner_security_group.id,
    security_group_id=app_security_group.id,
    description='SSH from GitHub Runner (Bastion)'
)

# Note: Keypair 'flatris-keypair' must exist in AWS
# Create it manually if needed:
#   aws ec2 create-key-pair --key-name flatris-keypair --query 'KeyMaterial' --output text > ~/.ssh/flatris-keypair.pem
#   chmod 400 ~/.ssh/flatris-keypair.pem

# User data script for Flatris App instance
app_user_data = """#!/bin/bash
# Update system
apt-get update -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
usermod -aG docker ubuntu

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Install Nginx
apt-get install -y nginx

# Create app directory
mkdir -p /home/ubuntu/flatris
chown -R ubuntu:ubuntu /home/ubuntu/flatris

echo "Flatris app instance ready!"
"""

# User data script for GitHub Runner instance
# Note: Token and configuration will be done via GitHub Actions workflow using secrets
runner_user_data = """#!/bin/bash
# Update system
apt-get update -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
usermod -aG docker ubuntu

# Install GitHub Actions Runner
cd /home/ubuntu
mkdir -p actions-runner
cd actions-runner

# Download latest runner
curl -o actions-runner-linux-x64-2.331.0.tar.gz -L https://github.com/actions/runner/releases/download/v2.331.0/actions-runner-linux-x64-2.331.0.tar.gz
echo "5fcc01bd546ba5c3f1291c2803658ebd3cedb3836489eda3be357d41bfcf28a7  actions-runner-linux-x64-2.331.0.tar.gz" | shasum -a 256 -c
tar xzf ./actions-runner-linux-x64-2.331.0.tar.gz

# Create config script that will be triggered via GitHub Actions
cat > /tmp/configure-runner.sh <<'EOF'

#!/bin/bash
cd /home/ubuntu/actions-runner
# Run config with token from environment
sudo ./config.sh --url https://github.com/kaziiriad/flatris --token $RUNNER_TOKEN
sudo ./run.sh
EOF

chmod +x /tmp/configure-runner.sh
chown -R ubuntu:ubuntu /home/ubuntu/actions-runner

echo "GitHub runner instance ready!"
echo "Runner will be configured via GitHub Actions workflow"
"""

# EC2 Instance for Flatris App
flatris_instance = aws.ec2.Instance(
    'flatris-app-instance',
    ami=ami,
    instance_type=instance_type,
    subnet_id=public_subnet.id,
    vpc_security_group_ids=[app_security_group.id],
    associate_public_ip_address=True,
    key_name=key_name,
    user_data=app_user_data,
    tags={
        'Name': 'flatris-app',
        'Project': 'Flatris',
        'Purpose': 'Web Application'
    }
)

# EC2 Instance for GitHub Actions Runner
runner_instance = aws.ec2.Instance(
    'flatris-runner-instance',
    ami=ami,
    instance_type=instance_type,
    subnet_id=public_subnet.id,
    vpc_security_group_ids=[runner_security_group.id],
    associate_public_ip_address=True,
    key_name=key_name,
    user_data=runner_user_data,
    tags={
        'Name': 'flatris-runner',
        'Project': 'Flatris',
        'Purpose': 'GitHub Actions Runner'
    }
)

# Outputs
pulumi.export('vpc_id', vpc.id)
pulumi.export('public_subnet_id', public_subnet.id)

pulumi.export('flatris_app_public_ip', flatris_instance.public_ip)
pulumi.export('flatris_app_public_dns', flatris_instance.public_dns)
pulumi.export('flatris_app_private_ip', flatris_instance.private_ip)

pulumi.export('runner_public_ip', runner_instance.public_ip)
pulumi.export('runner_public_dns', runner_instance.public_dns)
pulumi.export('runner_private_ip', runner_instance.private_ip)

# SSH to runner (bastion) directly
pulumi.export('ssh_to_runner', pulumi.Output.concat(
    'ssh -i ~/.ssh/', key_name, '.pem ubuntu@', runner_instance.public_ip
))

# SSH to flatris app via runner (bastion)
pulumi.export('ssh_to_flatris_via_runner', pulumi.Output.concat(
    'ssh -i ~/.ssh/', key_name, '.pem -J ubuntu@', runner_instance.public_ip, ' ubuntu@', flatris_instance.private_ip
))

# Flatris URL
pulumi.export('flatris_url', pulumi.Output.concat(
    'http://', flatris_instance.public_dns
))