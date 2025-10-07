from .modules.webhook_server import create_app
from .modules.bybit_trader import BybitTrader
from .modules.telegram_bot import TelegramBot
from .modules.logger import setup_logger
from .config.config import Config

logger = setup_logger(level=Config.LOG_LEVEL, log_file=Config.LOG_FILE)
telegram = TelegramBot(bot_token=Config.TELEGRAM_BOT_TOKEN, chat_id=Config.TELEGRAM_CHAT_ID, logger=logger)
trader = BybitTrader(api_key=Config.BYBIT_API_KEY, api_secret=Config.BYBIT_API_SECRET, default_leverage=Config.LEVERAGE_DEFAULT, test_mode=Config.TEST, logger=logger, notifier=telegram)

app = create_app(trader=trader, notifier=telegram, logger=logger)


