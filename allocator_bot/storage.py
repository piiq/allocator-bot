import json
import os

import boto3
from botocore.exceptions import ClientError

from .config import config


class LocalFileStorage:
    """Handles local file storage operations."""

    def __init__(self):
        if not config.data_folder_path:
            raise ValueError("data_folder_path is not configured")
        self.data_folder_path = config.data_folder_path
        if not os.path.exists(self.data_folder_path):
            os.makedirs(self.data_folder_path)
        self.allocations_file = os.path.join(self.data_folder_path, "allocations.json")
        self.tasks_file = os.path.join(self.data_folder_path, "tasks.json")

    def load_allocations(self) -> dict:
        """Load allocations from a local file."""
        if not os.path.exists(self.allocations_file):
            return {}
        with open(self.allocations_file, "r") as f:
            return json.load(f)

    def save_allocations(self, allocations: dict) -> None:
        """Save allocations to a local file."""
        with open(self.allocations_file, "w") as f:
            json.dump(allocations, f, indent=4)

    def load_tasks(self) -> dict:
        """Load tasks from a local file."""
        if not os.path.exists(self.tasks_file):
            return {}
        with open(self.tasks_file, "r") as f:
            return json.load(f)

    def save_tasks(self, tasks: dict) -> None:
        """Save tasks to a local file."""
        with open(self.tasks_file, "w") as f:
            json.dump(tasks, f, indent=4)


class CloudObjectStorage:
    """Handles cloud storage operations using S3."""

    def __init__(self):
        self.s3 = boto3.client(
            "s3",
            endpoint_url=config.s3_endpoint,
            aws_access_key_id=config.s3_access_key,
            aws_secret_access_key=config.s3_secret_key,
        )
        self.bucket_name = config.s3_bucket_name
        self.allocation_data_file = config.allocation_data_file
        self.task_data_file = config.task_data_file

    def load_allocations(self) -> dict:
        """Load allocations.json from S3 bucket."""
        try:
            obj = self.s3.get_object(
                Bucket=self.bucket_name, Key=self.allocation_data_file
            )
            return json.loads(obj["Body"].read().decode("utf-8"))
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return {}
            raise

    def save_allocations(self, allocations: dict) -> None:
        """Save allocations to S3 bucket."""
        self.s3.put_object(
            Bucket=config.s3_bucket_name,
            Key=self.allocation_data_file,
            Body=json.dumps(allocations, indent=4),
        )

    def load_tasks(self) -> dict:
        """Load tasks.json from S3 bucket."""
        try:
            obj = self.s3.get_object(Bucket=self.bucket_name, Key=self.task_data_file)
            return json.loads(obj["Body"].read().decode("utf-8"))
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return {}
            raise

    def save_tasks(self, tasks: dict) -> None:
        """Save tasks to S3 bucket."""
        self.s3.put_object(
            Bucket=self.bucket_name,
            Key=self.task_data_file,
            Body=json.dumps(tasks, indent=4),
        )


def get_storage() -> LocalFileStorage | CloudObjectStorage:
    """Get the appropriate storage class based on configuration."""
    if config.s3_enabled:
        return CloudObjectStorage()
    else:
        return LocalFileStorage()


def save_task(allocation_id: str, task_data: dict) -> str:
    """Save a new task."""
    storage: LocalFileStorage | CloudObjectStorage = get_storage()
    tasks = storage.load_tasks()
    tasks[allocation_id] = task_data
    storage.save_tasks(tasks)
    return allocation_id


def save_allocation(allocation_id: str, allocation_data: list[dict]) -> str:
    """Save the allocation to a json file."""
    storage: LocalFileStorage | CloudObjectStorage = get_storage()
    allocations = storage.load_allocations()
    allocations[allocation_id] = allocation_data
    storage.save_allocations(allocations)
    return allocation_id


def load_allocations() -> dict:
    """Load allocations from the configured storage."""
    storage: LocalFileStorage | CloudObjectStorage = get_storage()
    return storage.load_allocations()


def load_tasks() -> dict:
    """Load tasks from the configured storage."""
    storage: LocalFileStorage | CloudObjectStorage = get_storage()
    return storage.load_tasks()
