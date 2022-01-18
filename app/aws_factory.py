import boto3

from app.settings import LOCALSTACK, REGION, LOCALSTACK_ADDRESS
from logzero import logger


def get_aws_client(client_type: str):
    """Get an aws client configured to use LocalStack if env var is set"""
    if LOCALSTACK:
        logger.warn(f"Using localstack for {client_type} client")
        return boto3.client(
            client_type,
            region_name=REGION,
            endpoint_url=LOCALSTACK_ADDRESS,
            aws_access_key_id="foo",
            aws_secret_access_key="bar",
        )
    else:
        return boto3.client(client_type, REGION)


def get_aws_resource(resource_type: str):
    """Get an aws resource configured to use LocalStack if env var is set"""
    if LOCALSTACK:
        logger.warn(f"Using localstack for {resource_type} resource")
        return boto3.resource(
            resource_type,
            region_name=REGION,
            endpoint_url=LOCALSTACK_ADDRESS,
            aws_access_key_id="foo",
            aws_secret_access_key="bar",
        )
    else:
        return boto3.resource(resource_type, REGION)
