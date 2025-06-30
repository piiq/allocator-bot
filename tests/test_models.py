import pytest
from pydantic import ValidationError

from allocator_bot.models import AppConfig, TaskStructure


class TestAppConfig:
    """Test the AppConfig model validation."""

    def test_valid_config_with_s3_enabled(self):
        """Test valid configuration with S3 enabled."""

        # NOTE: pydantic does model validation in order of field declaration,
        #       so s3_enabled must be declared before data_folder_path.
        config = AppConfig(
            agent_host_url="http://localhost:8000",
            app_api_key="test-key",
            openrouter_api_key="test-key",
            s3_enabled=True,
            s3_endpoint="http://localhost:9000",
            s3_access_key="test-access-key",
            s3_secret_key="test-secret-key",
            s3_bucket_name="test-bucket",
            data_folder_path=None,  # Can be None when S3 is enabled
            fmp_api_key="test-fmp-key",
        )
        assert config.s3_enabled is True
        assert config.data_folder_path is None

    def test_valid_config_with_s3_disabled(self):
        """Test valid configuration with S3 disabled."""
        config = AppConfig(
            agent_host_url="http://localhost:8000",
            app_api_key="test-key",
            openrouter_api_key="test-key",
            data_folder_path="/tmp/test",
            s3_enabled=False,
            fmp_api_key="test-fmp-key",
        )
        assert config.s3_enabled is False
        assert config.data_folder_path == "/tmp/test"

    def test_data_folder_path_validation_s3_disabled(self):
        """Test data_folder_path validation when S3 is disabled."""
        with pytest.raises(ValidationError) as exc_info:
            AppConfig(
                agent_host_url="http://localhost:8000",
                app_api_key="test-key",
                openrouter_api_key="test-key",
                data_folder_path=None,  # Should fail when S3 is disabled
                s3_enabled=False,
                fmp_api_key="test-fmp-key",
            )
        assert "Data folder path must be set when S3 is not enabled" in str(
            exc_info.value
        )

    def test_s3_config_validation_s3_enabled(self):
        """Test S3 configuration validation when S3 is enabled."""
        # Test missing s3_endpoint
        with pytest.raises(ValidationError) as exc_info:
            AppConfig(
                agent_host_url="http://localhost:8000",
                app_api_key="test-key",
                openrouter_api_key="test-key",
                s3_enabled=True,
                s3_endpoint=None,  # Should fail when S3 is enabled
                s3_access_key="test-access-key",
                s3_secret_key="test-secret-key",
                s3_bucket_name="test-bucket",
                fmp_api_key="test-fmp-key",
            )
        assert "S3 configuration values must be set when S3 is enabled" in str(
            exc_info.value
        )

    def test_fmp_api_key_validation(self):
        """Test FMP API key validation."""
        with pytest.raises(ValidationError) as exc_info:
            AppConfig(
                agent_host_url="http://localhost:8000",
                app_api_key="test-key",
                openrouter_api_key="test-key",
                data_folder_path="/tmp/test",
                s3_enabled=False,
                fmp_api_key=None,  # Should fail
            )
        assert "FMP API key must be set for data retrieval" in str(exc_info.value)


class TestTaskStructure:
    """Test the TaskStructure model."""

    def test_task_structure_creation(self):
        """Test creating a TaskStructure with default values."""
        task = TaskStructure(
            task="Optimize portfolio",
            asset_symbols=["AAPL", "GOOGL", "MSFT"],
        )
        assert task.task == "Optimize portfolio"
        assert task.asset_symbols == ["AAPL", "GOOGL", "MSFT"]
        assert task.total_investment == 100000  # default
        assert task.start_date == "2019-01-01"  # default
        assert task.end_date is None  # default
        assert task.risk_free_rate == 0.05  # default
        assert task.target_return == 0.15  # default
        assert task.target_volatility == 0.15  # default

    def test_task_structure_with_custom_values(self):
        """Test creating a TaskStructure with custom values."""
        task = TaskStructure(
            task="Custom portfolio optimization",
            asset_symbols=["AAPL", "TSLA"],
            total_investment=50000,
            start_date="2020-01-01",
            end_date="2023-12-31",
            risk_free_rate=0.03,
            target_return=0.12,
            target_volatility=0.18,
        )
        assert task.task == "Custom portfolio optimization"
        assert task.asset_symbols == ["AAPL", "TSLA"]
        assert task.total_investment == 50000
        assert task.start_date == "2020-01-01"
        assert task.end_date == "2023-12-31"
        assert task.risk_free_rate == 0.03
        assert task.target_return == 0.12
        assert task.target_volatility == 0.18

    def test_task_structure_repr(self):
        """Test TaskStructure __repr__ method."""
        task = TaskStructure(
            task="Test task",
            asset_symbols=["AAPL"],
        )
        repr_str = repr(task)
        assert "TaskStructure" in repr_str
        assert "Test task" in repr_str
        assert "AAPL" in repr_str

    def test_task_structure_str(self):
        """Test TaskStructure __str__ method."""
        task = TaskStructure(
            task="Test task",
            asset_symbols=["AAPL", "GOOGL"],
        )
        str_repr = str(task)
        assert "Task structure:" in str_repr
        assert "Assets:['AAPL', 'GOOGL']" in str_repr
        assert "Total investment:100000" in str_repr

    def test_task_structure_pretty_dict(self):
        """Test TaskStructure __pretty_dict__ method."""
        task = TaskStructure(
            task="Test task",
            asset_symbols=["AAPL", "GOOGL"],
            total_investment=75000,
        )
        pretty_dict = task.__pretty_dict__()
        assert pretty_dict["Assets"] == "AAPL, GOOGL"
        assert pretty_dict["Total investment"] == 75000
        assert pretty_dict["Start date"] == "2019-01-01"
        assert pretty_dict["End date"] is None
        assert pretty_dict["Risk free rate"] == 0.05
        assert pretty_dict["Target return"] == 0.15
        assert pretty_dict["Target volatility"] == 0.15
