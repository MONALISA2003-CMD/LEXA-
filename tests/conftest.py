from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
for import_path in (str(API_ROOT), str(ROOT)):
    if import_path not in sys.path:
        sys.path.insert(0, import_path)
