import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class DataSaver:
    def __init__(self, data: list, output_dir: Path, filename: str):
        self.data = data
        self.output_dir = Path(output_dir)
        self.filename = filename

        self.output_dir.mkdir(exist_ok=True)

    def save_json(self) -> Path:
        filepath = self.output_dir / f"{self.filename}.json"

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

        logger.info("Saved %d records to %s", len(self.data), filepath)
        return filepath
