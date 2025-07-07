from pydantic import BaseModel, Field, field_validator


class AppConfig(BaseModel):
    """Application configuration loaded from environment variables."""

    agent_host_url: str = Field(
        description="The host URL and port number where the app is running."
    )
    app_api_key: str = Field(description="The API key to access the bot.")
    openrouter_api_key: str = Field(
        description="OpenRouter API key for AI functionality."
    )
    s3_enabled: bool | None = Field(
        default=False, description="Set to true to enable S3 storage."
    )
    s3_endpoint: str | None = Field(default=None, description="S3 endpoint URL.")
    s3_access_key: str | None = Field(default=None, description="S3 access key.")
    s3_secret_key: str | None = Field(default=None, description="S3 secret key.")
    s3_bucket_name: str | None = Field(default=None, description="S3 bucket name.")
    data_folder_path: str | None = Field(
        description="The path to the folder that will store the allocation data."
    )
    allocation_data_file: str = Field(
        default="allocations.json", description="Path to allocation file in S3."
    )
    task_data_file: str = Field(
        default="tasks.json", description="Path to task file in S3."
    )
    fmp_api_key: str | None = Field(
        default=None, description="Financial Modeling Prep API key for data retrieval."
    )

    @field_validator(
        "agent_host_url", "app_api_key", "openrouter_api_key", mode="before"
    )
    def validate_required_env_vars(cls, value: str | None, info) -> str | None:
        """Validate required environment variables.

        Raises ValueError if any required variable is not set.
        """
        if not value:
            raise ValueError(f"{info.field_name} environment variable is required.")
        return value

    @field_validator("data_folder_path")
    def validate_data_folder_path(cls, value: str | None, info) -> str | None:
        """Validate the data folder path.

        Must be set if S3 is not enabled, must be an absolute path, and must exist.
        Raises ValueError if the path is not valid.
        """
        if value is None and not info.data.get("s3_enabled", False):
            raise ValueError("Data folder path must be set when S3 is not enabled.")
        return value

    @field_validator("s3_endpoint", "s3_access_key", "s3_secret_key", "s3_bucket_name")
    def validate_s3_config(cls, value: str | None, info) -> str | None:
        """Validate S3 configuration values.

        If S3 is enabled, all values must be set and not None.
        If S3 is not enabled, these values can be None.
        """
        if value is None and info.data.get("s3_enabled", False):
            raise ValueError("S3 configuration values must be set when S3 is enabled.")
        return value

    @field_validator("fmp_api_key")
    def validate_fmp_api_key(cls, value: str | None) -> str | None:
        """Validate the Financial Modeling Prep API key.

        Must be set if FMP data retrieval is required.
        Raises ValueError if the key is not valid.
        """
        if value is None:
            raise ValueError("FMP API key must be set for data retrieval.")
        return value


class TaskStructure(BaseModel):
    task: str = Field(
        description="The task to perform. Human readable description of the task."
    )
    asset_symbols: list[str] = Field(
        description="A list of asset symbols to include in the portfolio. List of capitalized tickers."
    )
    total_investment: float | int = Field(
        description="The total investment amount to allocate to the portfolio.",
        default=100000,
    )
    start_date: str = Field(
        description="The start date of the portfolio simulation.",
        default="2019-01-01",
    )
    end_date: str | None = Field(
        description="The end date of the portfolio simulation.",
        default=None,
    )
    risk_free_rate: float = Field(
        description="The risk-free rate of the portfolio simulation. Normalized percentage to 1.",
        default=0.05,
    )
    target_return: float = Field(
        description="The target return of the portfolio simulation. Normalized percentage to 1.",
        default=0.15,
    )
    target_volatility: float = Field(
        description="The target volatility of the portfolio simulation. Normalized percentage to 1.",
        default=0.15,
    )

    def __repr__(self):
        return f"TaskStructure(task={self.task}, asset_symbols={self.asset_symbols}, total_investment={self.total_investment}, start_date={self.start_date}, end_date={self.end_date}, risk_free_rate={self.risk_free_rate}, target_return={self.target_return}, target_volatility={self.target_volatility})"

    def __str__(self):
        return f"Task structure:\nAssets:{self.asset_symbols}\nTotal investment:{self.total_investment}\nStart date:{self.start_date}\nEnd date:{self.end_date}\nRisk free rate:{self.risk_free_rate}\nTarget return:{self.target_return}\nTarget volatility:{self.target_volatility}"

    def __pretty_dict__(self):
        return {
            "Assets": ", ".join(self.asset_symbols),
            "Total investment": self.total_investment,
            "Start date": self.start_date,
            "End date": self.end_date,
            "Risk free rate": self.risk_free_rate,
            "Target return": self.target_return,
            "Target volatility": self.target_volatility,
        }
