import boto3
import os
import logging
from datetime import datetime

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    dynamodb_table = os.environ['DYNAMODB_TABLE_NAME']
    sns_topic_arn = os.environ['SNS_TOPIC_ARN']
    all_findings = ["Here is EC2 Instance Cleanup Report for all regions:"]

    ec2 = boto3.client('ec2')
    regions = [region['RegionName'] for region in ec2.describe_regions()['Regions']]

    for region in regions:
        try:
            ec2_client = boto3.client('ec2', region_name=region)
            dynamodb_client = boto3.client('dynamodb', region_name=region)

            # Check if DynamoDB table exists in the region
            try:
                dynamodb_client.describe_table(TableName=dynamodb_table)
                response = dynamodb_client.scan(TableName=dynamodb_table)
                for record in response['Items']:
                    finding_message = process_record(ec2_client, dynamodb_client, record, region, dynamodb_table)
                    if finding_message:
                        all_findings.append(f"Region: {region}, {finding_message}")
            except dynamodb_client.exceptions.ResourceNotFoundException:
                logger.info(f"DynamoDB table {dynamodb_table} not found in {region}")

        except Exception as e:
            logger.error(f"Error processing region {region}: {e}")

    if len(all_findings) > 1:
        consolidated_message = "\n".join(all_findings)
        sns_client = boto3.client('sns', region_name=os.environ['AWS_REGION'])
        sns_client.publish(TopicArn=sns_topic_arn, Message=consolidated_message)

    return {'statusCode': 200, 'body': 'EC2 instance cleanup across regions completed.'}

def process_record(ec2_client, dynamodb_client, record, region, table_name):
    instance_id = record['InstanceId']['S']
    timestamp = datetime.fromisoformat(record['Timestamp']['S'])

    if (datetime.utcnow() - timestamp).days >= 3:
        try:
            instance = ec2_client.describe_instances(InstanceIds=[instance_id])
            instance_state = instance['Reservations'][0]['Instances'][0]['State']['Name']

            if instance_state == 'stopped':
                ec2_client.terminate_instances(InstanceIds=[instance_id])
                dynamodb_client.delete_item(TableName=table_name, Key={'InstanceId': {'S': instance_id}})
                return f"Instance {instance_id} stopped for over 3 days, terminated and removed from DynamoDB."

            elif instance_state == 'running':
                dynamodb_client.delete_item(TableName=table_name, Key={'InstanceId': {'S': instance_id}})
                return f"Instance {instance_id} is running, removed from DynamoDB tracking."

        except Exception as e:
            logger.error(f"Error processing instance {instance_id} in {region}: {e}")
            return None

    return None