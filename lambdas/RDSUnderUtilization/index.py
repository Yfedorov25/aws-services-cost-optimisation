import boto3
import os
import logging
from datetime import datetime, timedelta

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    sns_topic_arn = os.environ['SNS_TOPIC_ARN']
    all_findings = ["Here is RDS Underutilization Report for all regions:"]

    # Get a list of all regions
    ec2_client = boto3.client('ec2')
    regions = [region['RegionName'] for region in ec2_client.describe_regions()['Regions']]

    for region in regions:
        logger.info(f"Checking region {region} for RDS instances")
        rds_client = boto3.client('rds', region_name=region)
        cw_client = boto3.client('cloudwatch', region_name=region)

        # Time range for metric evaluation
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=14)

        # Set thresholds for identifying underutilized instances
        thresholds = {
            'db.t3.micro': {'freeable_memory': 230 * 1024 * 1024, 'cpu': 15},
            'db.t2.micro': {'freeable_memory': 230 * 1024 * 1024, 'cpu': 15},
            'db.t3.small': {'freeable_memory': 800 * 1024 * 1024, 'cpu': 15},
            'db.t3.medium': {'freeable_memory': 2 * 1024 * 1024 * 1024, 'cpu': 15}
        }

        try:
            response = rds_client.describe_db_instances()
            for instance in response['DBInstances']:
                instance_id = instance['DBInstanceIdentifier']
                db_class = instance['DBInstanceClass']

                if db_class in thresholds:
                    freeable_memory = get_metric_average(cw_client, instance_id, 'FreeableMemory', start_time, end_time, 'Bytes')
                    cpu_utilization_avg = get_metric_average(cw_client, instance_id, 'CPUUtilization', start_time, end_time, 'Percent')
                    cpu_utilization_max = get_metric_maximum(cw_client, instance_id, 'CPUUtilization', start_time, end_time, 'Percent')

                    underutilized = freeable_memory > thresholds[db_class]['freeable_memory'] and cpu_utilization_avg < thresholds[db_class]['cpu']
                    if underutilized:
                        recommendation = "strongly recommended to downsize instance." if cpu_utilization_max < 50 else "recommended to figure out spikes reason and after that downsize instance."
                        message = f"Region: {region}, RDS Instance ID: {instance_id}, Type: {db_class} is underutilized. Freeable Memory: {round(freeable_memory / (1024 * 1024), 2)} MB, Average CPU Utilization: {round(cpu_utilization_avg, 2)}%, Maximum CPU Utilization: {round(cpu_utilization_max, 2)}%. It is {recommendation}"
                        all_findings.append(message)
                        logger.info(message)

        except Exception as e:
            logger.error(f"Error in region {region}: {e}")

    if len(all_findings) > 1:
        consolidated_message = "\n".join(all_findings)
        sns_client = boto3.client('sns')
        sns_client.publish(TopicArn=sns_topic_arn, Message=consolidated_message)

    return {'statusCode': 200, 'body': 'RDS underutilization evaluation across regions completed.'}

def get_metric_average(cw_client, instance_id, metric_name, start_time, end_time, unit):
    response = cw_client.get_metric_statistics(
        Namespace='AWS/RDS',
        MetricName=metric_name,
        Dimensions=[{'Name': 'DBInstanceIdentifier', 'Value': instance_id}],
        StartTime=start_time,
        EndTime=end_time,
        Period=3600,
        Statistics=['Average'],
        Unit=unit
    )
    datapoints = response.get('Datapoints', [])
    if datapoints:
        return sum(dp['Average'] for dp in datapoints) / len(datapoints)
    return 0

def get_metric_maximum(cw_client, instance_id, metric_name, start_time, end_time, unit):
    response = cw_client.get_metric_statistics(
        Namespace='AWS/RDS',
        MetricName=metric_name,
        Dimensions=[{'Name': 'DBInstanceIdentifier', 'Value': instance_id}],
        StartTime=start_time,
        EndTime=end_time,
        Period=3600,
        Statistics=['Maximum'],
        Unit=unit
    )
    datapoints = response.get('Datapoints', [])
    if datapoints:
        return max(dp['Maximum'] for dp in datapoints)
    return 0