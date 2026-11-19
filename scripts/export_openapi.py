import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.main import app

with open("openapi.json", "w", encoding="utf-8") as handle:
    json.dump(app.openapi(), handle, indent=2)
    handle.write("\n")

print("Exported openapi.json")
