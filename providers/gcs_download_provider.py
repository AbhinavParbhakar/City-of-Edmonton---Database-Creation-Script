from pathlib import Path
from typing import Protocol

from google.cloud import storage


class GCSDownloader(Protocol):
    def download_into(self, destination_folder: Path) -> None: ...


class GCSFolderDownloader:
    def __init__(self, bucket_name: str, prefix: str = "") -> None:
        self._bucket = storage.Client().bucket(bucket_name)
        self._prefix = prefix.strip("/")

    def download_into(self, destination_folder: Path) -> None:
        destination_folder.mkdir(parents=True, exist_ok=True)
        for blob in self._bucket.list_blobs(prefix=self._prefix):
            if blob.name.endswith("/"):
                continue
            local_path = destination_folder / Path(blob.name).name
            blob.download_to_filename(str(local_path))
