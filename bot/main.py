import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from telegram.ext import Application

# .env в корне проекта (при локальном запуске)
load_dotenv()
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from .handlers import register_handlers

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main() -> None:
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise SystemExit("Set BOT_TOKEN environment variable")
    # Таймаут загрузки медиа в Telegram API (изображения дополнительно сжимаются в handlers)
    app = (
        Application.builder()
        .token(token)
        .media_write_timeout(120)
        .write_timeout(90)
        .read_timeout(40)
        .build()
    )
    register_handlers(app)
    logger.info("Bot starting (polling)")
    app.run_polling(allowed_updates=["message", "callback_query", "poll_answer"])


if __name__ == "__main__":
    main()
