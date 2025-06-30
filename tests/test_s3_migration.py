import json
import os
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError


@pytest.fixture
def mock_s3_client():
    with patch("boto3.client") as mock_client:
        yield mock_client.return_value


@pytest.fixture
def mock_config_s3_enabled():
    """Mock config to enable S3 and set test values."""
    with patch("allocator_bot.storage.config") as mock_config_storage:
        mock_config_storage.s3_enabled = True
        mock_config_storage.s3_bucket_name = "test-bucket"
        mock_config_storage.allocation_data_file = "allocations.json"
        mock_config_storage.task_data_file = "tasks.json"
        mock_config_storage.s3_endpoint = "http://localhost:9000"
        mock_config_storage.s3_access_key = "test-access-key"
        mock_config_storage.s3_secret_key = "test-secret-key"
        mock_config_storage.fmp_api_key = "mock-api-key"
        mock_config_storage.data_folder_path = "/tmp"
        yield


async def test_save_and_load_allocations_s3(mock_s3_client, mock_config_s3_enabled):
    from allocator_bot.storage import load_allocations, save_allocation

    # Mock the get_object and put_object methods
    mock_s3_client.get_object.return_value = {
        "Body": MagicMock(read=lambda: json.dumps({}).encode("utf-8"))
    }

    allocation_id = "test_id_123"
    allocation_data = [{"Ticker": "AAPL", "Weight": 0.5, "Quantity": 10}]

    # Test saving to S3
    await save_allocation(allocation_id, allocation_data)

    # Verify put_object was called correctly
    mock_s3_client.put_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="allocations.json",
        Body=json.dumps({allocation_id: allocation_data}, indent=4),
    )

    # Test loading from S3
    mock_s3_client.get_object.return_value = {
        "Body": MagicMock(
            read=lambda: json.dumps({allocation_id: allocation_data}).encode("utf-8")
        )
    }
    loaded_allocations = await load_allocations()

    assert loaded_allocations == {allocation_id: allocation_data}


async def test_load_allocations_from_s3_no_key(mock_s3_client, mock_config_s3_enabled):
    from allocator_bot.storage import load_allocations

    # Simulate NoSuchKey error
    mock_s3_client.get_object.side_effect = ClientError(
        {"Error": {"Code": "NoSuchKey"}}, "GetObject"
    )

    loaded_allocations = await load_allocations()
    assert loaded_allocations == {}


@pytest.mark.parametrize(
    "s3_enabled, mock_s3_client",
    [(True, "mock_s3_client"), (False, None)],
    indirect=["mock_s3_client"],
)
async def test_save_allocation_s3_and_local(
    s3_enabled, mock_s3_client, tmp_path, monkeypatch
):
    # Mock the config values
    monkeypatch.setattr("allocator_bot.storage.config.s3_enabled", s3_enabled)
    monkeypatch.setattr("allocator_bot.storage.config.data_folder_path", str(tmp_path))
    monkeypatch.setattr(
        "allocator_bot.storage.config.allocation_data_file", "allocations.json"
    )
    monkeypatch.setattr("allocator_bot.storage.config.s3_bucket_name", "test-bucket")
    monkeypatch.setattr(
        "allocator_bot.storage.config.s3_endpoint", "http://localhost:9000"
    )
    monkeypatch.setattr("allocator_bot.storage.config.s3_access_key", "test-key")
    monkeypatch.setattr("allocator_bot.storage.config.s3_secret_key", "test-secret")

    from allocator_bot.storage import save_allocation

    if s3_enabled:
        # Mock S3 behavior
        mock_s3_client.get_object.return_value = {
            "Body": MagicMock(
                read=lambda: json.dumps(
                    {"existing_id": [{"Ticker": "GOOG", "Weight": 0.2}]}
                ).encode("utf-8")
            )
        }
    else:
        # Setup for local file test
        initial_data = {"existing_id": [{"Ticker": "GOOG", "Weight": 0.2}]}
        os.makedirs(tmp_path, exist_ok=True)
        with open(os.path.join(tmp_path, "allocations.json"), "w") as f:
            json.dump(initial_data, f)

    allocation_id = "new_test_id"
    allocation_data = [{"Ticker": "MSFT", "Weight": 0.8, "Quantity": 5}]

    await save_allocation(allocation_id, allocation_data)

    expected_data = {
        "existing_id": [{"Ticker": "GOOG", "Weight": 0.2}],
        "new_test_id": [{"Ticker": "MSFT", "Weight": 0.8, "Quantity": 5}],
    }

    if s3_enabled:
        # Verify S3 save was called correctly
        mock_s3_client.put_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="allocations.json",
            Body=json.dumps(expected_data, indent=4),
        )
    else:
        # Verify local file was updated
        with open(os.path.join(tmp_path, "allocations.json"), "r") as f:
            updated_data = json.load(f)
        assert updated_data == expected_data


async def test_local_file_storage_init_creates_directory(tmp_path, monkeypatch):
    """Test LocalFileStorage creates directory if it doesn't exist."""
    from allocator_bot.storage import LocalFileStorage

    storage_path = tmp_path / "new_storage_dir"
    assert not storage_path.exists()

    monkeypatch.setattr(
        "allocator_bot.storage.config.data_folder_path", str(storage_path)
    )

    storage = LocalFileStorage()
    assert storage_path.exists()
    assert storage.data_folder_path == str(storage_path)


async def test_local_file_storage_init_no_path():
    """Test LocalFileStorage raises error when data_folder_path is None."""
    from unittest.mock import patch

    from allocator_bot.storage import LocalFileStorage

    with patch("allocator_bot.storage.config.data_folder_path", None):
        with pytest.raises(ValueError, match="data_folder_path is not configured"):
            LocalFileStorage()


async def test_local_file_storage_load_nonexistent_allocations(tmp_path, monkeypatch):
    """Test loading allocations when file doesn't exist."""
    from allocator_bot.storage import LocalFileStorage

    monkeypatch.setattr("allocator_bot.storage.config.data_folder_path", str(tmp_path))

    storage = LocalFileStorage()
    allocations = await storage.load_allocations()
    assert allocations == {}


async def test_local_file_storage_load_nonexistent_tasks(tmp_path, monkeypatch):
    """Test loading tasks when file doesn't exist."""
    from allocator_bot.storage import LocalFileStorage

    monkeypatch.setattr("allocator_bot.storage.config.data_folder_path", str(tmp_path))

    storage = LocalFileStorage()
    tasks = await storage.load_tasks()
    assert tasks == {}


async def test_cloud_object_storage_s3_error_handling(
    mock_s3_client, mock_config_s3_enabled
):
    """Test CloudObjectStorage handles S3 errors properly."""
    from botocore.exceptions import ClientError

    from allocator_bot.storage import CloudObjectStorage

    storage = CloudObjectStorage()

    # Test S3 error other than NoSuchKey
    mock_s3_client.get_object.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied"}}, "GetObject"
    )

    with pytest.raises(ClientError):
        await storage.load_allocations()


async def test_cloud_object_storage_load_tasks_error(
    mock_s3_client, mock_config_s3_enabled
):
    """Test CloudObjectStorage handles task loading errors."""
    from botocore.exceptions import ClientError

    from allocator_bot.storage import CloudObjectStorage

    storage = CloudObjectStorage()

    # Test S3 error other than NoSuchKey
    mock_s3_client.get_object.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied"}}, "GetObject"
    )

    with pytest.raises(ClientError):
        await storage.load_tasks()


async def test_cloud_object_storage_load_tasks_no_key(
    mock_s3_client, mock_config_s3_enabled
):
    """Test CloudObjectStorage returns empty dict when tasks file doesn't exist."""
    from botocore.exceptions import ClientError

    from allocator_bot.storage import CloudObjectStorage

    storage = CloudObjectStorage()

    # Simulate NoSuchKey error for tasks
    mock_s3_client.get_object.side_effect = ClientError(
        {"Error": {"Code": "NoSuchKey"}}, "GetObject"
    )

    tasks = await storage.load_tasks()
    assert tasks == {}


async def test_save_task_function(mock_s3_client, mock_config_s3_enabled):
    """Test the save_task function."""
    from allocator_bot.storage import save_task

    # Mock existing tasks
    mock_s3_client.get_object.return_value = {
        "Body": MagicMock(
            read=lambda: json.dumps({"existing_task": {"data": "value"}}).encode(
                "utf-8"
            )
        )
    }

    task_id = "new_task_123"
    task_data = {"optimization": "max_sharpe", "symbols": ["AAPL", "GOOGL"]}

    result = await save_task(task_id, task_data)

    assert result == task_id
    mock_s3_client.put_object.assert_called_once()
    call_args = mock_s3_client.put_object.call_args
    assert call_args[1]["Bucket"] == "test-bucket"
    assert call_args[1]["Key"] == "tasks.json"

    saved_data = json.loads(call_args[1]["Body"])
    assert saved_data[task_id] == task_data
    assert "existing_task" in saved_data


async def test_load_tasks_function(mock_s3_client, mock_config_s3_enabled):
    """Test the load_tasks function."""
    from allocator_bot.storage import load_tasks

    expected_tasks = {"task1": {"data": "value1"}, "task2": {"data": "value2"}}
    mock_s3_client.get_object.return_value = {
        "Body": MagicMock(read=lambda: json.dumps(expected_tasks).encode("utf-8"))
    }

    tasks = await load_tasks()
    assert tasks == expected_tasks
