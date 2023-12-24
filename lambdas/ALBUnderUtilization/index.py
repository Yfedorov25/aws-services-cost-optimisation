import boto3
import os
import logging
import datetime
import json
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    sns_topic_arn = os.environ['SNS_TOPIC_ARN']
    sns_client = boto3.client('sns')
    all_findings = ["Here is ALB Underutilisation Report for all regions:"]

    # Get a list of all regions
    ec2_client = boto3.client('ec2')
    regions = [region['RegionName'] for region in ec2_client.describe_regions()['Regions']]

    # Iterate through each region
    for region in regions:
        logger.info(f"Checking region {region} for Elastic Load Balancers")
        elbv2_client = boto3.client('elbv2', region_name=region)
        cw_client = boto3.client('cloudwatch', region_name=region)

        paginator = elbv2_client.get_paginator('describe_load_balancers')
        page_iterator = paginator.paginate()

        for page in page_iterator:
            for elb in page['LoadBalancers']:
                elb_arn = elb['LoadBalancerArn']
                elb_name = elb['LoadBalancerName']

                target_groups = get_target_groups(elbv2_client, elb_arn)
                no_targets = check_no_targets(elbv2_client, target_groups)
                failed_targets = check_failed_targets(elbv2_client, target_groups)
                low_connection_count = check_low_connection_count(cw_client, elb_name)

                if no_targets or failed_targets or low_connection_count:
                    finding_message = create_detailed_message(region, elb_name, no_targets, failed_targets, low_connection_count)
                    all_findings.append(finding_message)

    if len(all_findings) > 1:
        consolidated_message = "\n".join(all_findings)
        sns_client.publish(TopicArn=sns_topic_arn, Message=consolidated_message)

    return "ELB evaluation across regions completed."

def get_target_groups(elbv2_client, load_balancer_arn):
    try:
        response = elbv2_client.describe_target_groups(LoadBalancerArn=load_balancer_arn)
        return response['TargetGroups']
    except ClientError as e:
        logger.error(f"Error retrieving target groups for ELB {load_balancer_arn}: {e}")
        return []

def check_no_targets(elbv2_client, target_groups):
    for target_group in target_groups:
        try:
            response = elbv2_client.describe_target_health(TargetGroupArn=target_group['TargetGroupArn'])
            if not response['TargetHealthDescriptions']:
                return True
        except ClientError as e:
            logger.error(f"Error checking targets for target group {target_group['TargetGroupArn']}: {e}")
    return False

def check_failed_targets(elbv2_client, target_groups):
    for target_group in target_groups:
        try:
            response = elbv2_client.describe_target_health(TargetGroupArn=target_group['TargetGroupArn'])
            if any(target['TargetHealth']['State'] == 'unhealthy' for target in response['TargetHealthDescriptions']):
                return True
        except ClientError as e:
            logger.error(f"Error checking target health for target group {target_group['TargetGroupArn']}: {e}")
    return False

def check_low_connection_count(cw_client, elb_name):
    try:
        end_time = datetime.datetime.now()
        start_time = end_time - datetime.timedelta(days=7)
        response = cw_client.get_metric_statistics(
            Namespace='AWS/ApplicationELB',
            MetricName='NewConnectionCount',
            Dimensions=[{'Name': 'LoadBalancer', 'Value': elb_name}],
            StartTime=start_time,
            EndTime=end_time,
            Period=86400,
            Statistics=['Sum']
        )
        total_connections = sum(datapoint['Sum'] for datapoint in response['Datapoints'])
        return total_connections < 20
    except ClientError as e:
        logger.error(f"Error checking connection count for ELB {elb_name}: {e}")
        return False

def create_detailed_message(region, elb_name, no_targets, failed_targets, low_connection_count):
    message_parts = [f"ELB '{elb_name}' in region '{region}' detected issues:"]
    if no_targets:
        message_parts.append("No targets in target groups associated.")
    if failed_targets:
        message_parts.append("Failed targets in target groups.")
    if low_connection_count:
        message_parts.append("Low connection count (< 20 connections per week).")
    return " ".join(message_parts)