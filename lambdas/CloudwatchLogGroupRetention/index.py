import boto3
import os
import logging
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    sns_topic_arn = os.environ['SNS_TOPIC_ARN']
    all_findings = ["Here is CloudWatch Log Group Retention Policy Update Report for all regions:"]

    # Get a list of all regions
    ec2_client = boto3.client('ec2')
    regions = [region['RegionName'] for region in ec2_client.describe_regions()['Regions']]

    for region in regions:
        logger.info(f"Checking region {region} for CloudWatch Log Groups")
        try:
            # Initialize clients for the specific region
            logs_client = boto3.client('logs', region_name=region)
            paginator = logs_client.get_paginator('describe_log_groups')
            page_iterator = paginator.paginate()

            updated_log_groups = []

            # Iterate through log groups with pagination
            for page in page_iterator:
                for log_group in page['logGroups']:
                    # Check if the retention policy is set
                    if 'retentionInDays' not in log_group:
                        # Set the retention policy to 14 days
                        logs_client.put_retention_policy(
                            logGroupName=log_group['logGroupName'],
                            retentionInDays=14
                        )
                        updated_log_groups.append(log_group['logGroupName'])
                        logger.info(f"Updated retention policy for {log_group['logGroupName']} in region {region}")

            if updated_log_groups:
                message = f"Region: {region}, Updated log groups with 14-day retention: {', '.join(updated_log_groups)}"
                all_findings.append(message)

        except ClientError as e:
            logger.error(f"An error occurred in region {region}: {e}")
            continue

    if len(all_findings) > 1:
        consolidated_message = "\n".join(all_findings)
        try:
            sns_client = boto3.client('sns')
            sns_client.publish(TopicArn=sns_topic_arn, Message=consolidated_message)
            logger.info("Sent SNS notification about updated log groups across all regions.")
        except ClientError as e:
            logger.error(f"An error occurred while sending SNS notification: {e}")

    return {"statusCode": 200, "body": "CloudWatch Log Group retention policy check completed across all regions."}
