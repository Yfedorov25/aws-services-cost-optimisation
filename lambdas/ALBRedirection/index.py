import boto3
import logging
import os

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    sns_topic_arn = os.environ['SNS_TOPIC_ARN']
    all_findings = ["Here is ALB HTTP to HTTPS Redirection Report for all regions:"]

    # Get a list of all regions
    ec2_client = boto3.client('ec2')
    regions = [region['RegionName'] for region in ec2_client.describe_regions()['Regions']]

    for region in regions:
        elb_client = boto3.client('elbv2', region_name=region)
        # List all Application Load Balancers (ALBs) in the current region
        albs = elb_client.describe_load_balancers()['LoadBalancers']
        modified_albs = []

        for alb in albs:
            if alb['Scheme'] == 'internet-facing':
                # Manage listeners for each ALB
                manage_alb_listeners(alb, modified_albs, elb_client, region)

        if modified_albs:
            all_findings.extend(modified_albs)

    # Send a notification if any ALBs were modified
    if len(all_findings) > 1:
        message = "\n".join(all_findings)
        sns_client = boto3.client('sns')
        sns_client.publish(TopicArn=sns_topic_arn, Message=message)
        logger.info("Notification sent to SNS topic.")

    return {
        'statusCode': 200,
        'body': 'Processed ALBs for HTTP to HTTPS redirection across all regions.'
    }

def manage_alb_listeners(alb, modified_albs, elb_client, region):
    listeners = elb_client.describe_listeners(LoadBalancerArn=alb['LoadBalancerArn'])['Listeners']
    http_listener = next((l for l in listeners if l['Protocol'] == 'HTTP'), None)
    https_listener = next((l for l in listeners if l['Protocol'] == 'HTTPS'), None)

    if https_listener and not http_listener:
        # Create HTTP listener
        create_http_listener(alb, elb_client, modified_albs, region)
    elif http_listener:
        # Modify existing HTTP listener
        modify_http_listener(http_listener, elb_client, modified_albs, region)

def create_http_listener(alb, elb_client, modified_albs, region):
    try:
        response = elb_client.create_listener(
            LoadBalancerArn=alb['LoadBalancerArn'],
            Protocol='HTTP',
            Port=80,
            DefaultActions=[
                {
                    'Type': 'redirect',
                    'RedirectConfig': {
                        'Protocol': 'HTTPS',
                        'Port': '443',
                        'StatusCode': 'HTTP_301'
                    }
                }
            ]
        )
        listener_arn = response['Listeners'][0]['ListenerArn']
        message = f"Region {region}: Created HTTP listener for ALB: {alb['LoadBalancerName']} (ARN: {listener_arn})"
        modified_albs.append(message)
    except Exception as e:
        logger.error(f"Error in region {region}: Failed to create HTTP listener for ALB: {alb['LoadBalancerName']} - {e}")

def modify_http_listener(http_listener, elb_client, modified_albs, region):
    try:
        elb_client.modify_listener(
            ListenerArn=http_listener['ListenerArn'],
            DefaultActions=[
                {
                    'Type': 'redirect',
                    'RedirectConfig': {
                        'Protocol': 'HTTPS',
                        'Port': '443',
                        'StatusCode': 'HTTP_301'
                    }
                }
            ]
        )
        message = f"Region {region}: Modified HTTP listener for ALB: {http_listener['ListenerArn']} to redirect to HTTPS"
        modified_albs.append(message)
    except Exception as e:
        logger.error(f"Error in region {region}: Failed to modify HTTP listener for ALB: {http_listener['ListenerArn']} - {e}")
