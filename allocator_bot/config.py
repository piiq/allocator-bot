import json
import os

import boto3
from botocore.exceptions import ClientError

from .models import AppConfig

config = AppConfig(
    agent_host_url=os.getenv("AGENT_HOST_URL"),
    app_api_key=os.getenv("APP_API_KEY"),
    data_folder_path=os.getenv("DATA_FOLDER_PATH", None),
    openrouter_api_key=os.getenv("OPENROUTER_API_KEY", None),
    s3_enabled=os.getenv("S3_ENABLED", "false").lower() == "true",
    s3_endpoint=os.getenv("S3_ENDPOINT", None),
    s3_access_key=os.getenv("S3_ACCESS_KEY", None),
    s3_secret_key=os.getenv("S3_SECRET_KEY", None),
    s3_bucket_name=os.getenv("S3_BUCKET_NAME", None),
    allocation_data_file=os.getenv("ALLOCATION_DATA_FILE", "allocations.json"),
    fmp_api_key=os.getenv("FMP_API_KEY", None),
)


def load_allocations_from_s3():
    """Load allocations.json from S3 bucket."""
    s3 = boto3.client(
        "s3",
        endpoint_url=config.s3_endpoint,
        aws_access_key_id=config.s3_access_key,
        aws_secret_access_key=config.s3_secret_key,
    )
    try:
        obj = s3.get_object(
            Bucket=config.s3_bucket_name, Key=config.allocation_data_file
        )
        return json.loads(obj["Body"].read().decode("utf-8"))
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            return {}
        else:
            raise


def save_allocations_to_s3(allocations: dict):
    """Save allocations to S3 bucket."""
    s3 = boto3.client(
        "s3",
        endpoint_url=config.s3_endpoint,
        aws_access_key_id=config.s3_access_key,
        aws_secret_access_key=config.s3_secret_key,
    )
    s3.put_object(
        Bucket=config.s3_bucket_name,
        Key=config.allocation_data_file,
        Body=json.dumps(allocations, indent=4),
    )
