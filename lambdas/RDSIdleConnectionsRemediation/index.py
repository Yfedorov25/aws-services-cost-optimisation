import boto3
import os
import logging
from datetime import datetime, timedelta
import json

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    sns_topic_arn = os.environ['SNS_TOPIC_ARN']
    dynamodb_table = os.environ['DYNAMODB_TABLE_NAME']
    sns_client = boto3.client('sns')
    all_findings = ["Here is EC2 Low Utilization Report for all regions:"]

    # Get a list of all regions
    ec2_client = boto3.client('ec2')
    regions = [region['RegionName'] for region in ec2_client.describe_regions()['Regions']]

    for region in regions:
        ec2_client = boto3.client('ec2', region_name=region)
        cw_client = boto3.client('cloudwatch', region_name=region)
        dynamodb_client = boto3.client('dynamodb', region_name=region)

        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=14)

        paginator = ec2_client.get_paginator('describe_instances')
        page_iterator = paginator.paginate(Filters=[{'Name': 'instance-state-name', 'Values': ['running']}])

        for page in page_iterator:
            for reservation in page['Reservations']:
                for instance in reservation['Instances']:
                    instance_id = instance['InstanceId']
                    cpu_stats = fetch_cloudwatch_metrics(cw_client, 'CPUUtilization', instance_id, start_time, end_time)
                    network_in_stats = fetch_cloudwatch_metrics(cw_client, 'NetworkIn', instance_id, start_time, end_time)

                    avg_cpu_utilization = calculate_average(cpu_stats)
                    avg_network_io = calculate_average(network_in_stats)

                    if avg_cpu_utilization <= 10 and avg_network_io <= 5 * 1024 * 1024:  # 5 MB in Bytes
                        finding_message = f"Region: {region}, Instance {instance_id}: Stopped due to low utilization. It will be deleted if not restarted within 3 days. If this instance is no longer needed - leave it in stopped state."
                        all_findings.append(finding_message)
                        stop_instance_and_record(ec2_client, dynamodb_client, dynamodb_table, instance_id)

    if len(all_findings) > 1:
        consolidated_message = "\n".join(all_findings)
        sns_client.publish(TopicArn=sns_topic_arn, Message=consolidated_message)

    return {'statusCode': 200, 'body': 'EC2 evaluation across regions completed.'}

def fetch_cloudwatch_metrics(cw_client, metric_name, instance_id, start_time, end_time):
    try:
        response = cw_client.get_metric_statistics(
            Namespace='AWS/EC2',
            MetricName=metric_name,
            Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
            StartTime=start_time,
            EndTime=end_time,
            Period=86400,
            Statistics=['Average']
        )
        return response['Datapoints']
    except Exception as error:
        logger.error(f"Error fetching metrics for instance {instance_id}: {error}")
        return []

def calculate_average(datapoints):
    if not datapoints:
        return 0
    total = sum([dp['Average'] for dp in datapoints])
    return total / len(datapoints)

def stop_instance_and_record(ec2_client, dynamodb_client, dynamodb_table, instance_id):
    try:
        ec2_client.stop_instances(InstanceIds=[instance_id])
        logger.info(f"Instance {instance_id} stopped due to low utilization.")
        dynamodb_client.put_item(
            TableName=dynamodb_table,
            Item={
                'InstanceId': {'S': instance_id},
                'Timestamp': {'S': datetime.utcnow().isoformat()},
                'Note': {'S': 'Instance stopped due to low utilization.'}
            }
        )
    except Exception as error:
        logger.error(f"Error processing instance {instance_id}: {error}")