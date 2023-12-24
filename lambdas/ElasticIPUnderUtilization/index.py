import boto3
import os
import logging
import json

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    sns_topic_arn = os.environ['SNS_TOPIC_ARN']
    sns_client = boto3.client('sns')
    ec2_client = boto3.client('ec2')

    regions = [region['RegionName'] for region in ec2_client.describe_regions()['Regions']]
    all_findings = []

    for region in regions:
        logger.info(f"Checking region {region} for Elastic IPs")
        ec2_client = boto3.client('ec2', region_name=region)
        eips = ec2_client.describe_addresses()['Addresses']

        for eip in eips:
            if 'InstanceId' not in eip or (eip['InstanceId'] and ec2_client.describe_instances(InstanceIds=[eip['InstanceId']])['Reservations'][0]['Instances'][0]['State']['Name'] == 'stopped'):
                finding = f"Region {region}: Elastic IP {eip['PublicIp']} is either unassociated or associated with a stopped instance. It is strongly recommended to release Elastic IP to avoid unneccessary costs "
                all_findings.append(finding)

    if all_findings:
        message = "Here is Unassociated Elastic IP Report for all regions:\n" + "\n".join(all_findings)
        sns_client.publish(TopicArn=sns_topic_arn, Message=message)

    return {"statusCode": 200, "body": "Elastic IP check completed."}