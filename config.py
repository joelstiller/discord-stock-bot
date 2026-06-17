from dotenv import load_dotenv
import os

load_dotenv()

DISCORD_TOKEN: str = os.environ["DISCORD_TOKEN"]
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "deepseek-r1:32b")
STONKS_CHANNEL_NAME: str = os.getenv("STONKS_CHANNEL_NAME", "stonks")
POLL_INTERVAL_SECONDS: int = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))
