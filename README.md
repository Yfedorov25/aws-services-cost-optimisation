# AWS Lambda Functions for Resource and Cost Optimization

## Overview
This repository comprises a series of AWS Lambda functions and CloudFormation templates designed for resource optimization, cost reduction, and compliance across various AWS services. Each function addresses specific operational aspects, enhancing efficiency and security within the AWS environment.

## Table of Contents
- [Solutions Overview](#solutions-overview)
- [Usage Instructions](#usage-instructions)
- [Deployment Instructions](#deployment-instructions)
- [Solutions Description](#solutions-description)
- [Contributing](#contributing)

## Solutions Overview
The `aws-lambda-cost-optimization` repository includes the following solutions:
1. ALB Redirection Check
2. CloudWatch Logs Retention Check
3. RDS Underutilization Check
4. RDS High Utilization Check
5. RDS Idle Connections Check (Parts 1 & 2)
6. EC2 Low Utilization Check (Parts 1 & 2)
7. ECS Service Underutilization Check
8. ELB Underutilization Check
9. Elastic IP Check

Each solution is stored in separate folders within the repository and includes a CloudFormation template and corresponding Lambda function code.

## Usage Instructions
To deploy these solutions:
1. Navigate to the desired solution's folder.
2. Review and update the CloudFormation template and Lambda function as needed.
3. Deploy the template using the AWS Management Console, AWS CLI, or your preferred deployment tool.

## Deployment Instructions

This repository is configured with a GitHub Actions workflow to automate the deployment of solutions. To utilize this automated deployment:

1. **Configure GitHub Secrets**:
    - Go to your GitHub repository's settings.
    - Access the "Secrets" section.
    - Add the following secrets for secure AWS access:
        - `AWS_ACCESS_KEY_ID`: Your AWS access key ID.
        - `AWS_SECRET_ACCESS_KEY`: Your AWS secret access key.
    Ensure these credentials have the necessary permissions to deploy the CloudFormation templates.

2. **Set Environment Variables**:
    - Confirm that the `STACK_NAME`, `S3_BUCKET_NAME`, and `AWS_DEFAULT_REGION` environment variables are appropriately set in the GitHub Actions workflow file.

3. **Triggering the Deployment**:
    - Make required changes to the CloudFormation templates or Lambda functions and commit these changes to the `main` branch.
    - This action will trigger the GitHub Actions workflow, which performs the following tasks:
        - Checks out the repository.
        - Sets up Python 3.8.
        - Installs the AWS SAM CLI.
        - Configures AWS credentials using the provided secrets.
        - Builds the SAM application in the `./cloudformation` directory.
        - Deploys the application using SAM to create or update the specified CloudFormation stack.

4. **Monitoring the Deployment**:
    - Monitor the deployment process via the Actions tab in the GitHub repository following your push to `main`.

## Solutions Description

### 1. ALB Redirection Check
**Purpose:** Automates HTTP to HTTPS redirection configuration in Application Load Balancers.

**Features:**
- Scans ALBs and configures redirection rules.
- Scheduled checks every 4 days.
- Utilizes SNS for notifications.

**Use Case:** Ideal for maintaining security and compliance by ensuring all web traffic is encrypted using HTTPS.

### 2. CloudWatch Logs Retention Check
**Purpose:** Standardizes retention policy across CloudWatch Log Groups.

**Features:**
- Regularly reviews log groups for retention settings.
- Ensures compliance with retention policies.
- Scheduled to run every 6 hours.

**Use Case:** Essential for organizations needing to comply with data retention regulations and manage logging costs effectively.

### 3. RDS Underutilization Check
**Purpose:** Identifies underutilized RDS instances for cost optimization.

**Features:**
- Analyzes RDS instances for low resource utilization.
- Suggests potential downsizing opportunities.
- Runs every 7 days.

**Use Case:** Perfect for reducing costs by identifying and resizing or terminating underused RDS instances.

### 4. RDS High Utilization Check
**Purpose:** Monitors RDS instances for signs of overutilization.

**Features:**
- Tracks high CPU and storage usage.
- Helps in proactive capacity management.
- Scheduled checks every 6 hours.

**Use Case:** Critical for preventing performance bottlenecks by identifying and addressing high utilization in RDS instances.

### 5. & 6. RDS Idle Connections Check and Remediation
**Purpose (Part 1):** Identifies and manages idle RDS instances.
**Purpose (Part 2):** Performs cleanup and remediation for idle RDS instances.

**Features:**
- Detects RDS instances with no active connections.
- Automates DB snapshot creation and instance stopping.
- Deletes idle RDS instances based on DynamoDB metadata.
- Runs every 6 hours.

**Use Case:** Ideal for optimizing RDS costs by identifying idle instances, safely stopping them, and eventually removing them if they remain unused.

### 7. & 8. EC2 Low Utilization Check and Remediation
**Purpose (Part 1):** Identifies EC2 instances with low utilization metrics.
**Purpose (Part 2):** Handles remediation for underutilized EC2 instances.

**Features:**
- Monitors EC2 instances for low CPU and network usage.
- Terminates or stops EC2 instances based on usage metrics.
- Records findings in DynamoDB and runs daily checks.

**Use Case:** Suitable for optimizing EC2 costs by monitoring usage patterns, and automatically stopping or terminating instances that are consistently underutilized.

### 9. ECS Service Underutilization Check
**Purpose:** Ensures efficient utilization of ECS services.

**Features:**
- Evaluates ECS services for resource usage.
- Aids in optimizing service scaling.
- Runs every 3 days.

**Use Case:** Optimal for ECS cost management by scaling down or removing underutilized services.

### 10. ELB Underutilization Check
**Purpose:** Identifies underutilized Elastic Load Balancers.

**Features:**
- Monitors and reports underused ELBs.
- Aims to reduce unnecessary costs.
- Scheduled checks every 3 days.

**Use Case:** Beneficial for maintaining cost-effective load balancing by identifying and addressing underused ELBs.

### 11. Elastic IP Check
**Purpose:** Monitors and manages underutilized Elastic IPs.

**Features:**
- Detects unassociated or idle Elastic IPs.
- Helps avoid unnecessary charges.
- Runs every 3 days.

**Use Case:** Crucial for avoiding extra costs associated with unutilized Elastic IPs.

## Contributing
I welcome contributions to this repository. If you have suggestions or improvements, please submit a pull request or open an issue.
   