import os

from dotenv import load_dotenv

from .models import AppConfig

load_dotenv()

config = AppConfig(
    agent_host_url=os.getenv("AGENT_HOST_URL", ""),
    app_api_key=os.getenv("APP_API_KEY", ""),
    data_folder_path=os.getenv("DATA_FOLDER_PATH", None),
    openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
    s3_enabled=os.getenv("S3_ENABLED", "false").lower() == "true",
    s3_endpoint=os.getenv("S3_ENDPOINT", None),
    s3_access_key=os.getenv("S3_ACCESS_KEY", None),
    s3_secret_key=os.getenv("S3_SECRET_KEY", None),
    s3_bucket_name=os.getenv("S3_BUCKET_NAME", None),
    allocation_data_file=os.getenv("ALLOCATION_DATA_FILE", "allocations.json"),
    task_data_file=os.getenv("TASK_DATA_FILE", "tasks.json"),
    fmp_api_key=os.getenv("FMP_API_KEY", None),
)
