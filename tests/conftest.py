"""测试公共配置。"""

from pathlib import Path
import os
import sys


# Unit/integration tests are deterministic and offline by default.  Live API,
# OASIS and judge smokes have dedicated scripts and must never be triggered
# merely because a developer has a populated root .env file.
os.environ.setdefault("MIRO_DISABLE_DOTENV", "true")


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
APP_DIR = BACKEND_DIR / "app"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
