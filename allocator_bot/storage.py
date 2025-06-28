import json

import boto3
import pandas as pd
from botocore.exceptions import ClientError

from .config import config


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


def load_allocations_from_file(file_path: str):
    """Load allocations from a local file."""
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_allocations_to_file(file_path: str, allocations: dict):
    """Save allocations to a local file."""
    with open(file_path, "w") as f:
        json.dump(allocations, f, indent=4)

def get_all_allocations():
    """Load all allocations and format them for display."""
    if config.s3_enabled:
        allocations_data = load_allocations_from_s3()
    else:
        allocations_data = load_allocations_from_file(
            f"{config.data_folder_path}/allocations.json"
        )

    if not allocations_data:
        return []

    processed_allocations = []
    for allocation_id, allocation_details in allocations_data.items():
        # Most of the times there is only one allocation per id, but sometimes there are more
        if not isinstance(allocation_details, list):
            allocation_details = [allocation_details]

        for allocation in allocation_details:
            task_params = {
                key: value
                for key, value in allocation.items()
                if key not in ["Ticker", "Weight", "Quantity"]
            }
            processed_allocations.append(
                {
                    "allocation_id": allocation_id,
                    "symbols": ", ".join(allocation.get("asset_symbols", [])) if "asset_symbols" in allocation else "N/A",
                    "investment_amount": allocation.get("total_investment", "N/A"),
                    "holding_period": f"{allocation.get('start_date', 'N/A')} - {allocation.get('end_date', 'N/A')}",
                    "task_parameters": json.dumps(task_params),
                }
            )

    df = pd.DataFrame(processed_allocations)
    return df.to_dict(orient="records")
