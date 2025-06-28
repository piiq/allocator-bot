import json
import os
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError


@pytest.fixture
def mock_s3_client():
    with patch("boto3.client") as mock_client:
        yield mock_client.return_value


@pytest.fixture()
def mock_config_s3_enabled():
    with patch("allocator_bot.config.config") as mock_config:
        mock_config.s3_enabled = True
        mock_config.s3_bucket_name = "test-bucket"
        mock_config.allocation_data_file = "allocations.json"
        mock_config.s3_endpoint = "http://localhost:9000"
        mock_config.s3_access_key = "test-access-key"
        mock_config.s3_secret_key = "test-secret-key"
        mock_config.fmp_api_key = "mock-api-key"
        mock_config.data_folder_path = "/tmp"
        yield mock_config


def test_save_and_load_allocations_s3(mock_s3_client, mock_config_s3_enabled):
    from allocator_bot.config import load_allocations_from_s3
    from allocator_bot.portfolio import save_allocation

    # Mock the get_object and put_object methods
    mock_s3_client.get_object.return_value = {
        "Body": MagicMock(read=lambda: json.dumps({}).encode("utf-8"))
    }

    allocation_id = "test_id_123"
    allocation_data = [{"Ticker": "AAPL", "Weight": 0.5, "Quantity": 10}]

    # Test saving to S3
    save_allocation(allocation_id, allocation_data)

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
    loaded_allocations = load_allocations_from_s3()

    assert loaded_allocations == {allocation_id: allocation_data}


def test_load_allocations_from_s3_no_key(mock_s3_client, mock_config_s3_enabled):
    from allocator_bot.config import load_allocations_from_s3

    # Simulate NoSuchKey error
    mock_s3_client.get_object.side_effect = ClientError(
        {"Error": {"Code": "NoSuchKey"}}, "GetObject"
    )

    loaded_allocations = load_allocations_from_s3()
    assert loaded_allocations == {}


@pytest.mark.parametrize(
    "s3_enabled, mock_s3_client",
    [(True, "mock_s3_client"), (False, None)],
    indirect=["mock_s3_client"],
)
def test_save_allocation_s3_and_local(
    s3_enabled, mock_s3_client, tmp_path, monkeypatch
):
    monkeypatch.setattr("allocator_bot.portfolio.config.s3_enabled", s3_enabled)
    monkeypatch.setattr(
        "allocator_bot.portfolio.config.data_folder_path", str(tmp_path)
    )
    monkeypatch.setattr(
        "allocator_bot.portfolio.config.allocation_data_file", "allocations.json"
    )
    monkeypatch.setattr("allocator_bot.portfolio.config.s3_bucket_name", "test-bucket")

    from allocator_bot.portfolio import save_allocation

    if s3_enabled:
        # Mock S3 behavior
        mock_s3_client.get_object.return_value = {
            "Body": MagicMock(read=lambda: json.dumps({}).encode("utf-8"))
        }
        # Set a dummy loader and saver to isolate the test
        monkeypatch.setattr(
            "allocator_bot.portfolio.load_allocations_from_s3",
            lambda: {"existing_id": [{"Ticker": "GOOG", "Weight": 0.2}]},
        )
        monkeypatch.setattr(
            "allocator_bot.portfolio.save_allocations_to_s3", MagicMock()
        )

    else:
        # Setup for local file test
        initial_data = {"existing_id": [{"Ticker": "GOOG", "Weight": 0.2}]}
        with open(os.path.join(tmp_path, "allocations.json"), "w") as f:
            json.dump(initial_data, f)

    allocation_id = "new_test_id"
    allocation_data = [{"Ticker": "MSFT", "Weight": 0.8, "Quantity": 5}]

    save_allocation(allocation_id, allocation_data)

    if s3_enabled:
        # Verify S3 save was called correctly
        from allocator_bot.portfolio import save_allocations_to_s3

        expected_s3_data = {
            "existing_id": [{"Ticker": "GOOG", "Weight": 0.2}],
            "new_test_id": [{"Ticker": "MSFT", "Weight": 0.8, "Quantity": 5}],
        }
        save_allocations_to_s3.assert_called_once_with(expected_s3_data)
    else:
        # Verify local file was updated
        with open(os.path.join(tmp_path, "allocations.json"), "r") as f:
            updated_data = json.load(f)

        expected_local_data = {
            "existing_id": [{"Ticker": "GOOG", "Weight": 0.2}],
            "new_test_id": [{"Ticker": "MSFT", "Weight": 0.8, "Quantity": 5}],
        }
        assert updated_data == expected_local_data
