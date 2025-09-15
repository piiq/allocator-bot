import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

import aiohttp
import boto3  # type: ignore
from botocore.exceptions import ClientError  # type: ignore
from openbb_fmp import FMPEquityHistoricalFetcher

from .models import AppConfig


async def check_openrouter(api_key: str) -> None:
    """Validate OpenRouter reachability and API key.

    Performs a lightweight GET to the models endpoint. Raises RuntimeError on failure.
    """
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is missing.")

    # Ensure downstream libs that rely on env var can see it
    os.environ["OPENROUTER_API_KEY"] = api_key

    timeout = aiohttp.ClientTimeout(total=5)
    headers = {"Authorization": f"Bearer {api_key}"}
    url = "https://openrouter.ai/api/v1/key"
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    return
                if resp.status in (401, 403):
                    raise RuntimeError(
                        "OpenRouter validation failed: unauthorized. Check OPENROUTER_API_KEY."
                    )
                raise RuntimeError(
                    f"OpenRouter validation failed: HTTP {resp.status}. Service may be unavailable."
                )
    except asyncio.TimeoutError as e:
        raise RuntimeError("OpenRouter validation failed: request timed out.") from e
    except aiohttp.ClientError as e:
        raise RuntimeError(f"OpenRouter validation failed: {e}") from e


def check_s3(endpoint: str, access_key: str, secret_key: str, bucket: str) -> None:
    """Validate S3/compatible storage credentials and bucket access.

    Calls head_bucket and a zero-key list to confirm access. Raises RuntimeError on failure.
    """
    try:
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
        # Existence and access
        s3.head_bucket(Bucket=bucket)
        # Minimal read attempt
        s3.list_objects_v2(Bucket=bucket, MaxKeys=0)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "Unknown")
        msg = e.response.get("Error", {}).get("Message", str(e))
        raise RuntimeError(f"S3 validation failed: {code} - {msg}") from e
    except Exception as e:  # pragma: no cover - safety net
        raise RuntimeError(f"S3 validation failed: {e}") from e


def check_local_storage(path: str) -> None:
    """Ensure local storage path exists and is writable.

    Creates the folder if missing and performs a write test.
    """
    if not path:
        raise RuntimeError("DATA_FOLDER_PATH must be set when S3 is disabled.")

    try:
        os.makedirs(path, exist_ok=True)
    except OSError as e:
        raise RuntimeError(f"Failed to create data folder at '{path}': {e}") from e

    test_file = os.path.join(path, ".allocator_bot_write_test")
    try:
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
    except OSError as e:
        raise RuntimeError(f"Data folder is not writable at '{path}': {e}") from e


async def check_fmp(key: str) -> None:
    """Validate FMP key by fetching a tiny slice of data.

    Uses OpenBB FMP fetcher for a single symbol and short date window.
    """
    if not key:
        raise RuntimeError("FMP_API_KEY is missing.")

    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=5)

    try:
        data = await FMPEquityHistoricalFetcher.fetch_data(
            params={
                "symbol": "AAPL",
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            credentials={"fmp_api_key": key},
        )
        # Some accounts may have limited history; consider any non-exception as success
        if data is None:
            raise RuntimeError("FMP validation failed: empty response.")
    except Exception as e:
        raise RuntimeError(
            "FMP validation failed: invalid key or network error."
        ) from e


async def validate_environment(config: AppConfig) -> None:
    """Run all environment validations. Raises on first failure.

    Set VALIDATION_SKIP=true to bypass in development environments.
    """
    if os.getenv("VALIDATION_SKIP", "false").lower() == "true":
        logging.warning("VALIDATION_SKIP=true: Skipping external credential checks.")
        return

    # OpenRouter
    await check_openrouter(config.openrouter_api_key)

    # Storage
    if config.s3_enabled:
        check_s3(
            endpoint=str(config.s3_endpoint),
            access_key=str(config.s3_access_key),
            secret_key=str(config.s3_secret_key),
            bucket=str(config.s3_bucket_name),
        )
    else:
        if config.data_folder_path is None:
            raise RuntimeError("DATA_FOLDER_PATH must be set when S3 is not enabled.")
        check_local_storage(config.data_folder_path)

    # FMP
    await check_fmp(str(config.fmp_api_key))

    logging.info("Environment validation succeeded.")
