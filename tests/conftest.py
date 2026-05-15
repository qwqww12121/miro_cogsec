"""测试公共配置。"""

from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
APP_DIR = BACKEND_DIR / "app"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
