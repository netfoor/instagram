import logging
import json
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataSaver: 
    
    def __init__(self, data, output_dir: Path, filename: str):
        self.data = data
        self.output_dir = Path(output_dir)
        self.filename = filename 

        self.output_dir.mkdir(exist_ok=True)
        


    
    def save_json(self):
        filepath = self.output_dir / f"{self.filename}.json"

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.data, indent=2, ensure_ascii=False)

            logger.info(f"Saved {len(self.data)} records to {filepath}")

            return filepath