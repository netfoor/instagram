"""Utilities for saving scraped data to disk."""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class DataSaver:
    """Saves structured data (lists of dicts) as JSON files.

    Creates the output directory if it doesn't exist, then writes
    pretty-printed JSON with UTF-8 encoding.

    Example::

        saver = DataSaver(data=users, filename="followers", output_dir=Path("data"))
        saver.save_json()  # writes data/followers.json
    """

    def __init__(self, data: list, output_dir: Path, filename: str):
        """
        Args:
            data: List of records to save (typically list[dict]).
            output_dir: Directory where the JSON file will be written.
            filename: Name of the file without extension (e.g. "followers").
        """
        self.data = data
        self.output_dir = Path(output_dir)
        self.filename = filename

        self.output_dir.mkdir(exist_ok=True)

    def save_json(self) -> Path:
        """Write data to ``<output_dir>/<filename>.json``.

        Returns:
            Path to the written file.
        """
        filepath = self.output_dir / f"{self.filename}.json"

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

        logger.info("Saved %d records to %s", len(self.data), filepath)
        return filepath
