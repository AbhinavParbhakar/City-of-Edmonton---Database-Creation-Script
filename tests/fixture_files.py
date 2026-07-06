"""Locates the Excel files the tests run against, downloading them from GCS
into a local cache folder when they are not already present.

Environment (via .env or the shell):
    MIOVISION_GCS_BUCKET  -- bucket holding scraped studies; unset means the
                             cache folder must already be populated
    TEST_GCS_PREFIX       -- which scraper run to test against
    TEST_FIXTURES_FOLDER  -- local cache folder (gitignored)

The studies under the prefix must have been loaded into the database the
tests connect to, since the tests compare these files (and the live
Miovision pages for the same study ids) against database contents.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

from providers.gcs_download_provider import GCSFolderDownloader

DEFAULT_TEST_GCS_PREFIX = "raw/run_id=1782892801"
DEFAULT_FIXTURES_FOLDER = "tests/fixtures"


def fixtures_folder() -> Path:
    load_dotenv()
    return Path(os.environ.get("TEST_FIXTURES_FOLDER", DEFAULT_FIXTURES_FOLDER))


def fixture_files() -> list[Path]:
    folder = fixtures_folder()
    files = sorted(folder.glob("*.xlsx")) if folder.is_dir() else []

    if not files:
        bucket = os.environ.get("MIOVISION_GCS_BUCKET")
        if bucket is None:
            raise Exception(
                f"No fixture files in {folder} and MIOVISION_GCS_BUCKET is not set."
            )
        prefix = os.environ.get("TEST_GCS_PREFIX", DEFAULT_TEST_GCS_PREFIX)
        GCSFolderDownloader(bucket_name=bucket, prefix=prefix).download_into(folder)
        files = sorted(folder.glob("*.xlsx"))

        if not files:
            raise Exception(f"No .xlsx files found under gs://{bucket}/{prefix}")

    return files
