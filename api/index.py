import os
import sys
from pathlib import Path

# Function bundle layout (local repo and serverless task dir both preserve this relative
# structure): <root>/api/index.py → repo root is two levels up from this file.
_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(_ROOT / "backend"))

# The relative default ("data/snapshots/latest") also works because the serverless CWD is
# the project root; the __file__-anchored override removes any CWD dependence.
os.environ.setdefault("WINDLENS_DATA_MODE", "snapshot")
os.environ.setdefault("WINDLENS_SNAPSHOT_DIR", str(_ROOT / "data" / "snapshots" / "latest"))

from app.main import app  # noqa: E402
