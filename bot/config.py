"""Bot configuration loaded from environment variables."""
import os
from dotenv import load_dotenv
load_dotenv()

def _get_env(name: str, default: str | None = None, required: bool = False) -> str:
    value = os.getenv(name, default)
    if required and not value:
        raise RuntimeError(f"Переменная окружения '{name}' не задана.")
    return value

BOT_TOKEN: str = _get_env("BOT_TOKEN", required=True)
ADMIN_ID: int = int(_get_env("ADMIN_ID", default="0"))
ADMIN_IDS = {int(x.strip()) for x in _get_env("ADMIN_IDS", default="").split(",") if x.strip().isdigit()}
if ADMIN_ID:
    ADMIN_IDS.add(ADMIN_ID)
DATABASE_URL: str = _get_env("DATABASE_URL", required=True)
NICKNAME_MIN_LENGTH = 3
NICKNAME_MAX_LENGTH = 20
AGE_MIN = 6
AGE_MAX = 99
PASSWORD_MIN_LENGTH = 4
PASSWORD_MAX_LENGTH = 64
START_MONEY = 1000
START_STARS = 0
BOT_USERNAME: str = _get_env("BOT_USERNAME", default="").lstrip("@")
