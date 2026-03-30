import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN: str = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_USER_ID: int = int(os.environ["TELEGRAM_USER_ID"])

OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen3:4b")

BASE_DIR = Path(os.getenv("BASE_DIR", "/opt/assistant"))
VAULT_PATH = BASE_DIR / "vault"
DB_PATH = BASE_DIR / "data" / "assistant.db"
LOG_PATH = BASE_DIR / "data" / "logs"
CACHE_PATH = BASE_DIR / "data" / "cache"
PROMPTS_PATH = BASE_DIR / "prompts"

TIMEZONE: str = os.getenv("TIMEZONE", "UTC")
ASSISTANT_NAME: str = os.getenv("ASSISTANT_NAME", "Tintu")
