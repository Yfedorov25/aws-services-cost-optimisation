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
    all_findings = ["Here is RDS Service Underutilization Report for all regions:"]

    # Get a list of all regions
    ec2_client = boto3.client('ec2')
    regions = [region['RegionName'] for region in ec2_client.describe_regions()['Regions']]

    for region in regions:
        cloudwatch = boto3.client('cloudwatch', region_name=region)
        dynamodb = boto3.client('dynamodb', region_name=region)
        rds = boto3.client('rds', region_name=region)
        sns = boto3.client('sns', region_name=region)

        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=14)

        try:
            db_instances = rds.describe_db_instances()['DBInstances']
            for db_instance in db_instances:
                db_instance_id = db_instance['DBInstanceIdentifier']
                response = cloudwatch.get_metric_statistics(
                    Namespace='AWS/RDS',
                    MetricName='DatabaseConnections',
                    Dimensions=[{'Name': 'DBInstanceIdentifier', 'Value': db_instance_id}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=86400,
                    Statistics=['Maximum']
                )
                max_connections = max([dp['Maximum'] for dp in response['Datapoints']], default=0)
                if max_connections == 0:
                    snapshot_name = f'{db_instance_id}-lambda-snapshot'
                    rds.create_db_snapshot(DBInstanceIdentifier=db_instance_id, DBSnapshotIdentifier=snapshot_name)
                    rds.stop_db_instance(DBInstanceIdentifier=db_instance_id)

                    message = f"Region: {region}, RDS instance {db_instance_id} has been stopped due to inactivity. A snapshot has been taken."
                    all_findings.append(message)

                    dynamodb.put_item(
                        TableName=dynamodb_table,
                        Item={
                            'DBInstanceIdentifier': {'S': db_instance_id},
                            'DBSnapshotIdentifier': {'S': snapshot_name},
                            'Timestamp': {'S': datetime.utcnow().isoformat()},
                            'Note': {'S': 'Instance stopped due to inactivity'}
                        }
                    )
        except Exception as e:
            logger.error(f"Error in region {region}: {e}")

    if len(all_findings) > 1:
        consolidated_message = "\n".join(all_findings)
        sns.publish(TopicArn=sns_topic_arn, Message=consolidated_message)

    return {'statusCode': 200, 'body': 'RDS evaluation across regions completed.'}

