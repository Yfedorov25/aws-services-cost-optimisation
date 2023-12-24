import boto3
import os
import datetime
import logging
import json
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    sns_topic_arn = os.environ['SNS_TOPIC_ARN']
    all_findings = ["Here is ECS Service Underutilisation Report for all regions:"]

    # Get a list of all regions
    ec2_client = boto3.client('ec2')
    regions = [region['RegionName'] for region in ec2_client.describe_regions()['Regions']]

    for region in regions:
        logger.info(f"Checking ECS services in region {region}")
        ecs = boto3.client('ecs', region_name=region)
        cw = boto3.client('cloudwatch', region_name=region)

        try:
            paginator_clusters = ecs.get_paginator('list_clusters')
            cluster_pages = paginator_clusters.paginate()

            for cluster_page in cluster_pages:
                clusters = cluster_page['clusterArns']
                for cluster in clusters:
                    cluster_name = cluster.split('/')[-1]  # Extract the cluster name
                    paginator_services = ecs.get_paginator('list_services')
                    service_pages = paginator_services.paginate(cluster=cluster)

                    for service_page in service_pages:
                        services = service_page['serviceArns']
                        for service in services:
                            service_name = service.split('/')[-1]  # Extract the service name
                            findings = process_service(cluster_name, service_name, region, cw)
                            if findings:
                                all_findings.extend(findings)

        except ClientError as e:
            logger.error(f"Error in Lambda execution: {e}")

    if len(all_findings) > 1:
        consolidated_message = "\n".join(all_findings)
        sns = boto3.client('sns')
        sns.publish(TopicArn=sns_topic_arn, Message=consolidated_message)

    return {'statusCode': 200, 'body': json.dumps('Lambda function execution completed.')}

def process_service(cluster, service, region, cw):
    findings = []
    try:
        logger.info(f"Processing service: {service} in cluster: {cluster}")

        start_time = datetime.datetime.now() - datetime.timedelta(days=14)
        end_time = datetime.datetime.now()

        cpu_dimensions = [
            {'Name': 'ClusterName', 'Value': cluster},
            {'Name': 'ServiceName', 'Value': service}
        ]
        memory_dimensions = [
            {'Name': 'ClusterName', 'Value': cluster},
            {'Name': 'ServiceName', 'Value': service}
        ]

        cpu_utilization = get_metric_statistics(cw, 'AWS/ECS', 'CPUUtilization', cpu_dimensions, start_time, end_time)
        memory_utilization = get_metric_statistics(cw, 'AWS/ECS', 'MemoryUtilization', memory_dimensions, start_time, end_time)

        if check_utilization(cpu_utilization) and check_utilization(memory_utilization):
            message = build_message(cluster, service, region, cpu_utilization, memory_utilization)
            findings.append(message)

    except ClientError as e:
        logger.error(f"Error processing service {service} in cluster {cluster}: {e}")
    return findings

def get_metric_statistics(cw_client, namespace, metric_name, dimensions, start_time, end_time):
    return cw_client.get_metric_statistics(
        Namespace=namespace,
        MetricName=metric_name,
        Dimensions=dimensions,
        StartTime=start_time,
        EndTime=end_time,
        Period=86400,
        Statistics=['Average']
    )

def check_utilization(metric_data):
    if 'Datapoints' in metric_data and metric_data['Datapoints']:
        avg_utilization = sum(d['Average'] for d in metric_data['Datapoints']) / len(metric_data['Datapoints'])
        return avg_utilization < 20
    return False

def build_message(cluster, service, region, cpu_utilization, memory_utilization):
    avg_cpu = sum(d['Average'] for d in cpu_utilization['Datapoints']) / len(cpu_utilization['Datapoints'])
    avg_memory = sum(d['Average'] for d in memory_utilization['Datapoints']) / len(memory_utilization['Datapoints'])
    return (f"ECS Service '{service}' in the cluster '{cluster}' and region '{region}' has consistently "
            f"recorded low resource utilization over the past two weeks. CPU Usage: {avg_cpu}%, Memory Usage: {avg_memory}%. "
            f"Consider downsizing or removing it if not needed.")
