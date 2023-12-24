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
    all_findings = ["Here is RDS High Utilization Report for all regions:"]

    # Get a list of all regions
    ec2_client = boto3.client('ec2')
    regions = [region['RegionName'] for region in ec2_client.describe_regions()['Regions']]

    for region in regions:
        rds_client = boto3.client('rds', region_name=region)
        cw_client = boto3.client('cloudwatch', region_name=region)

        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=2)

        thresholds = {
            'db.t3.micro': {'freeable_memory': 100, 'cpu': 50},
            'db.t2.micro': {'freeable_memory': 100, 'cpu': 50},
            'db.t3.small': {'freeable_memory': 200, 'cpu': 50},
            'db.t3.medium': {'freeable_memory': 400, 'cpu': 50}
        }

        try:
            response = rds_client.describe_db_instances()
            for instance in response['DBInstances']:
                instance_id = instance['DBInstanceIdentifier']
                db_class = instance['DBInstanceClass']
                findings = evaluate_instance_metrics(cw_client, instance_id, start_time, end_time, db_class, thresholds, region)

                if findings:
                    all_findings.extend(findings)

        except Exception as e:
            logger.error(f"Error in region {region}: {e}")

    if len(all_findings) > 1:
        consolidated_message = "\n".join(all_findings)
        sns_client = boto3.client('sns')
        sns_client.publish(TopicArn=sns_topic_arn, Message=consolidated_message)

    return {'statusCode': 200, 'body': 'RDS evaluation across regions completed.'}

def evaluate_instance_metrics(cw_client, instance_id, start_time, end_time, db_class, thresholds, region):
    findings = []
    metrics = {
        'ReadIOPS': {'threshold': 900, 'statistic': 'Maximum'},
        'WriteIOPS': {'threshold': 900, 'statistic': 'Maximum'},
        'SwapUsage': {'threshold': 400000000, 'statistic': 'Maximum'}
    }

    freeable_memory = get_metric_average(cw_client, 'AWS/RDS', 'FreeableMemory', instance_id, start_time, end_time)
    cpu_utilization = get_metric_average(cw_client, 'AWS/RDS', 'CPUUtilization', instance_id, start_time, end_time)

    if db_class in thresholds:
        if freeable_memory is not None and freeable_memory < thresholds[db_class]['freeable_memory']:
            findings.append(f"Region: {region}, RDS Instance ID: {instance_id} has low freeable memory ({freeable_memory} MB).")
        if cpu_utilization is not None and cpu_utilization > thresholds[db_class]['cpu']:
            findings.append(f"Region: {region}, RDS Instance ID: {instance_id} has high CPU utilization ({cpu_utilization}%).")

    for metric_name, details in metrics.items():
        metric_value = get_metric_max(cw_client, 'AWS/RDS', metric_name, instance_id, start_time, end_time, details['statistic'])
        if metric_value > details['threshold']:
            findings.append(f"Region: {region}, RDS Instance ID: {instance_id} triggered alarm for {metric_name} with value {metric_value}")

    return findings

def get_metric_average(cw_client, namespace, metric_name, instance_id, start_time, end_time):
    response = cw_client.get_metric_statistics(
        Namespace=namespace,
        MetricName=metric_name,
        Dimensions=[{'Name': 'DBInstanceIdentifier', 'Value': instance_id}],
        StartTime=start_time,
        EndTime=end_time,
        Period=3600,
        Statistics=['Average']
    )
    datapoints = response.get('Datapoints', [])
    if datapoints:
        return sum(dp['Average'] for dp in datapoints) / len(datapoints)
    return 0

def get_metric_max(cw_client, namespace, metric_name, instance_id, start_time, end_time, statistic):
    response = cw_client.get_metric_statistics(
        Namespace=namespace,
        MetricName=metric_name,
        Dimensions=[{'Name': 'DBInstanceIdentifier', 'Value': instance_id}],
        StartTime=start_time,
        EndTime=end_time,
        Period=3600,
        Statistics=[statistic]
    )
    datapoints = response.get('Datapoints', [])
    return max([dp[statistic] for dp in datapoints], default=0) if datapoints else 0
